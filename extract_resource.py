"""
extract_resource.py  —  Extractor for "Artem Skakunov's resource file" format
Tested against resource.dat from Little Bomber (Alawar Entertainment, ~2003).
Requires Python 3.6+, no third-party dependencies.

Usage:
    python extract_resource.py resource.dat
    python extract_resource.py resource.dat --out my_folder
    python extract_resource.py resource.dat --list
"""

import argparse
import struct
import sys
import zlib
from pathlib import Path

HEADER_MAGIC = b"Artem Skakunov's resource file\r\n"  # 32 bytes


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

class ResourceEntry:
    """Represents one record from the TOC."""
    __slots__ = (
        "name", "filename", "offset", "compressed_size",
        # image-only fields (None for text/INI entries)
        "sprite_type", "has_transparency",
        "tile_height", "frame_width", "frame_height",
    )

    def __init__(self, name, filename, offset, compressed_size,
                 sprite_type=None, has_transparency=None,
                 tile_height=None, frame_width=None, frame_height=None):
        self.name             = name
        self.filename         = filename
        self.offset           = offset
        self.compressed_size  = compressed_size
        self.sprite_type      = sprite_type
        self.has_transparency = has_transparency
        self.tile_height      = tile_height
        self.frame_width      = frame_width
        self.frame_height     = frame_height

    @property
    def is_image(self):
        return self.sprite_type is not None

    def __repr__(self):
        return (f"<ResourceEntry name={self.name!r} file={self.filename!r} "
                f"offset={self.offset} size={self.compressed_size}>")


def parse(path: Path):
    """
    Parse a resource.dat file.

    Returns:
        (entries: list[ResourceEntry], data_blob: bytes)
        where data_blob is the raw byte region from which entries are extracted.
    """
    data = path.read_bytes()

    # --- header ---
    if not data.startswith(HEADER_MAGIC):
        raise ValueError(
            f"{path}: not an Artem Skakunov resource file "
            f"(bad magic, got {data[:32]!r})"
        )

    # --- TOC compressed size (uint16 LE at offset 0x20) ---
    toc_csize = struct.unpack_from("<H", data, 0x20)[0]
    toc_start = 0x22                        # right after the 2-byte length field
    toc_end   = toc_start + toc_csize

    if toc_end > len(data):
        raise ValueError("TOC compressed size exceeds file size — file truncated?")

    # --- decompress TOC ---
    try:
        toc_bytes = zlib.decompress(data[toc_start:toc_end])
    except zlib.error as exc:
        raise ValueError(f"Failed to decompress TOC: {exc}") from exc

    # --- data region starts right after the TOC zlib stream ---
    data_blob = data[toc_end:]

    # --- parse TOC lines ---
    toc_text = toc_bytes.decode("utf-8", errors="replace")
    entries  = []
    for lineno, raw_line in enumerate(toc_text.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]

        if len(parts) == 4:
            # Text / INI / WAV / etc.
            name, filename, offset, compressed_size = parts
            entries.append(ResourceEntry(
                name             = name,
                filename         = filename,
                offset           = int(offset),
                compressed_size  = int(compressed_size),
            ))

        elif len(parts) == 9:
            # BMP sprite / image
            (name, filename,
             sprite_type, has_transparency,
             tile_height, frame_width, frame_height,
             offset, compressed_size) = parts
            entries.append(ResourceEntry(
                name             = name,
                filename         = filename,
                offset           = int(offset),
                compressed_size  = int(compressed_size),
                sprite_type      = int(sprite_type),
                has_transparency = int(has_transparency),
                tile_height      = int(tile_height),
                frame_width      = int(frame_width),
                frame_height     = int(frame_height),
            ))

        else:
            print(f"  [warn] line {lineno}: unexpected field count "
                  f"({len(parts)}), skipping: {line!r}", file=sys.stderr)

    return entries, data_blob


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract_entry(entry: ResourceEntry, data_blob: bytes) -> bytes:
    """Decompress and return the raw bytes for a single entry."""
    chunk = data_blob[entry.offset : entry.offset + entry.compressed_size]
    if len(chunk) != entry.compressed_size:
        raise ValueError(
            f"Entry {entry.name!r}: expected {entry.compressed_size} bytes "
            f"at offset {entry.offset}, got {len(chunk)}"
        )
    try:
        return zlib.decompress(chunk)
    except zlib.error as exc:
        raise ValueError(
            f"Entry {entry.name!r}: decompression failed: {exc}"
        ) from exc


def extract_all(entries, data_blob: bytes, out_dir: Path, verbose: bool = True):
    """Extract every entry into out_dir, preserving the original filenames."""
    out_dir.mkdir(parents=True, exist_ok=True)

    ok = 0
    errors = 0
    for entry in entries:
        try:
            raw = extract_entry(entry, data_blob)
        except ValueError as exc:
            print(f"  [error] {exc}", file=sys.stderr)
            errors += 1
            continue

        # Use the original filename from the TOC.
        # If two logical names share the same filename (e.g. wall_shadow aliases),
        # the file will simply be written once — the content is identical.
        dest = out_dir / entry.filename
        dest.write_bytes(raw)
        if verbose:
            tag = "image" if entry.is_image else "data "
            print(f"  [{tag}] {entry.name:<40s}  ->  {entry.filename}  "
                  f"({entry.compressed_size} -> {len(raw)} bytes)")
        ok += 1

    return ok, errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_list(entries, data_blob):
    """Print the TOC in a human-readable table."""
    print(f"{'NAME':<40}  {'FILENAME':<35}  {'CSIZE':>8}  TYPE / SPRITE INFO")
    print("-" * 110)
    for e in entries:
        if e.is_image:
            extra = (f"sprite_type={e.sprite_type}  transp={e.has_transparency}  "
                     f"tile_h={e.tile_height}  frm_w={e.frame_width}  frm_h={e.frame_height}")
        else:
            extra = "text/data"
        print(f"{e.name:<40}  {e.filename:<35}  {e.compressed_size:>8}  {extra}")
    print(f"\nTotal: {len(entries)} entries")


def main():
    ap = argparse.ArgumentParser(
        description="Extract files from Artem Skakunov's resource.dat format."
    )
    ap.add_argument("input",  type=Path, help="Path to resource.dat")
    ap.add_argument("--out",  type=Path, default=None,
                    help="Output directory (default: <input_stem>_extracted/)")
    ap.add_argument("--list", action="store_true",
                    help="List TOC contents without extracting")
    ap.add_argument("--quiet", action="store_true",
                    help="Suppress per-file output")
    args = ap.parse_args()

    if not args.input.is_file():
        print(f"Error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing {args.input} ...")
    try:
        entries, data_blob = parse(args.input)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"  {len(entries)} entries found, data region: {len(data_blob):,} bytes")

    if args.list:
        print()
        cmd_list(entries, data_blob)
        return

    out_dir = args.out or args.input.parent / (args.input.stem + "_extracted")
    print(f"Extracting to {out_dir} ...")
    ok, errors = extract_all(entries, data_blob, out_dir, verbose=not args.quiet)
    print(f"\nDone: {ok} extracted, {errors} errors.")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
