# SkitchG

A fast, minimal, Skitch-inspired image annotation app for Linux.

Open an image, drag a big pink arrow onto it, hit `Ctrl+C`, paste it in a chat
or ticket. That's the whole point.

![SkitchG](skitchg.png)

## Features

- **Skitch-style arrows** — thick, tapered shaft, big filled head, white
  outline + drop shadow so they read on any background
- Text (bold, outlined), rectangle, ellipse, line, freehand pen
- Pixelate tool for hiding sensitive information
- Crop
- Select / move / reshape annotations with handles
- Full undo/redo
- Copy the rendered image straight to the clipboard
- Export as PNG or JPEG — the original file is never touched unless you
  explicitly confirm overwriting it
- Opens `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp` (respects EXIF rotation)

Annotations are vector objects while you edit — they are only rasterized when
you save or copy.

## Install & run

Requires Python 3.10+ and PySide6.

```bash
cd SkitchG
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# run
.venv/bin/python app.py [image.jpg]
# or
./skitchg-launcher.sh image.jpg
```

### Desktop integration (optional)

```bash
./install-desktop.sh
```

This installs a `skitchg` command in `~/.local/bin`, a launcher in the
application menu, and registers SkitchG for "Open with…" on image files.

## Usage

| Key | Action |
|---|---|
| `V` | Select / move |
| `A` | **Arrow** |
| `L` | Line |
| `R` | Rectangle |
| `E` | Ellipse |
| `P` | Pen |
| `T` | Text |
| `X` | Pixelate |
| `C` | Crop |
| `Ctrl+O` | Open |
| `Ctrl+S` | Save (defaults to `name_annotated.png`) |
| `Ctrl+Shift+S` | Save As |
| `Ctrl+C` | Copy rendered image to clipboard |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Undo / Redo |
| `Delete` | Delete selected annotation |
| `Esc` | Cancel current action / deselect |
| `Ctrl+scroll` | Zoom, `Ctrl+0` fit, `Ctrl+1` 100% |

**Arrows:** select the arrow tool, click where the tail starts and drag toward
the thing you're pointing at. Click an existing arrow (with the select tool)
to move it, or drag its endpoint handles to reshape it.

**Text:** select the text tool, click, type. `Enter` commits, `Shift+Enter`
makes a new line, `Esc` cancels. Double-click existing text to edit it.

**Colors & sizes:** pick from the swatches in the top bar (default: strong
pink). `S`/`M`/`L` buttons set stroke thickness and text size. The outline
button toggles the white outline + shadow. With annotations selected, these
change the selection; otherwise they set the style for new annotations.

Note: on Linux the clipboard content is owned by the app — keep SkitchG open
until you've pasted, or run a clipboard manager.

## Project layout

```text
app.py                  entry point
skitchg/
  main_window.py        menus, toolbars, open/save/copy
  canvas.py             QGraphicsView canvas + tool interaction
  items.py              vector annotation items (arrow, text, …)
  commands.py           undo/redo commands
  export.py             flatten image + annotations for save/copy
  icons.py              programmatically drawn icons
  palette.py            colors, stroke sizes, constants
```

## Non-goals

No cloud, no accounts, no OCR, no layers, no filters, no image editing.
It's an annotation tool.
