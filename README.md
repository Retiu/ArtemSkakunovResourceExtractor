# ArtemSkakunovResourceExtractor

A Python extraction tool for **"Artem Skakunov's resource file"**. This filetype is a custom archive format for game assets used in at least one title developed by Artem Skakunov, *Little Bombers Returns*, published by Alawar Entertainment in 2004.

No prior documentation of this format existed. The format was reverse-engineered from scratch by examining `resource.dat` across multiple copies of the game.

This script has been used to extract the soundtrack of Little Bombers Returns and is available at https://downloads.khinsider.com/game-soundtracks/album/little-bombers-returns-windows-gamerip-2004 upon approval.

> **Note:** This tool was partially written by [Claude](https://claude.ai) (Anthropic). The format research and reverse engineering was done collaboratively.

---

## Format summary

```
Offset  Size  Description
------  ----  -----------
0x00    32    ASCII magic: "Artem Skakunov's resource file\r\n"
0x20    2     uint16 LE — compressed byte length of the TOC block
0x22    N     zlib stream — TOC (decompresses to UTF-8 CSV lines)
0x22+N  ...   Data region — sequential zlib-compressed entry blobs
```

The TOC contains one entry per line, in one of two formats:

**Text/data entry (4 fields):**
```
name,filename,offset,compressed_size
```

**Image/sprite entry (9 fields):**
```
name,filename,sprite_type,has_transparency,tile_height,frame_width,frame_height,offset,compressed_size
```

| Field | Values | Meaning |
|---|---|---|
| `sprite_type` | 0, 1, 2 | 0 = background/tile, 1 = normal sprite, 2 = special |
| `has_transparency` | 0, 1 | 1 = image uses transparency (typically 24 bpp BMP) |
| `tile_height` | 16, 32, 64 | Height of one tile/frame cell in pixels |
| `frame_width` | 0 or N | Nonzero = horizontal animation strip; frame count = image_width / N |
| `frame_height` | 0 or N | Nonzero = 2D sprite sheet grid; rows = image_height / N |

All entries (`offset`, `compressed_size`) reference the data region. Every blob is a standalone zlib stream that decompresses to the raw file (BMP, WAV, INI, S3M, TXT, etc.).

---

## Requirements

- Python 3.6+
- No third-party dependencies

---

## Usage

```
extract_resource.py [-h] [--out OUT] [--list] [--quiet] input

Extract files from Artem Skakunov's resource.dat format.

positional arguments:
  input       Path to resource.dat

options:
  -h, --help  show this help message and exit
  --out OUT   Output directory (default: <input_stem>_extracted/)
  --list      List TOC contents without extracting
  --quiet     Suppress per-file output
```

---

## Known versions

Two distinct builds of `resource.dat` have been observed:

| Build | Entries | Notes |
|---|---|---|
| Full/registered | 336 | All 9 stages, all enemies, audio files, `door.bmp` |
| Demo | 313 | Missing stage 9 walls, enemy 20, some boss sprites and extras |

Both use the identical format and are handled by the same script.

---

## License

MIT
