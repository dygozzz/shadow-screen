# Shadow Screen

A fast, friendly replacement for EPOMAKER's *Image Custom Tool* that uploads GIFs to the
1.14" screen of the **EPOMAKER Shadow-S (wired/USB, `320F:5055`)**.

It runs in Chrome or Edge through WebHID, so you don't need drivers, admin rights, or the
official tool.

## Features

- Drag and drop a GIF, WebP, PNG or JPG
- Real-size preview at 240×135, quantized to the screen's RGB565 colors
- Framing: **cover**, **contain** (blurred or solid background) or **stretch**, plus drag to pan, scroll to zoom, mirror and rotate 180°
- Up to 50 frames, sampled evenly across the whole GIF (or a trimmed range) so animations aren't cut short
- Original or custom frame interval
- Progress bar and ETA, and the keyboard clock is synced on every upload

## Usage

1. Close VIA and Image Custom Tool, since they hold the same HID interface.
2. Run `Abrir Shadow Screen.cmd`. It serves the folder on `http://localhost:8765` with Python's
   built-in HTTP server and opens it. WebHID needs a secure context, and `localhost` counts as one.
3. Click **Conectar teclado**, pick the Shadow-S, drop a GIF and hit **Enviar**.

Any static server works too, for example `python -m http.server 8765 --bind 127.0.0.1`.

## How it works

The protocol was reverse-engineered by hooking the official tool's HID I/O with Frida. See
[PROTOCOL.md](PROTOCOL.md) for the details. `tools/` contains the Python reference
implementation and the capture scripts.

## Disclaimer

This is an unofficial project with no affiliation to EPOMAKER. It writes to the keyboard's flash
using the same packets the official tool sends. Use it at your own risk.
