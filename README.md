# Shadow Screen

A fast, friendly replacement for EPOMAKER's *Image Custom Tool* that uploads GIFs to the
1.14" screen of the **EPOMAKER Shadow-S (wired/USB, `320F:5055`)**.

It runs in Chrome or Edge through WebHID, so you don't need drivers, admin rights, or the
official tool.

## Features

- **Queue** of GIFs and images that plays on the keyboard by itself, from its own flash, with
  no PC app running. Reorder and remove items, and a meter shows the 50-frame budget.
- Real-size preview at 240×135, quantized to the screen's RGB565 colors, per item or for the whole queue
- Per-item framing: **cover**, **contain** (blurred or solid background) or **stretch**, plus drag to pan, scroll to zoom, mirror and rotate 180°
- GIFs: frames sampled evenly across the whole GIF (or a trimmed range), so animations aren't cut short
- Images: time on screen (an images-only queue becomes a slideshow, one frame per image)
- Progress bar and ETA, and the keyboard clock is synced on every upload

### Keyboard limits

The firmware stores **one animation of up to 50 frames with a single interval**. A queue is
packed into those 50 frames. In a mixed queue the interval comes from the GIF, so a still image
repeats its frame to stay on screen longer, and that uses up budget.

## Usage

1. Close VIA and Image Custom Tool, since they hold the same HID interface.
2. Run `Instalar atalhos.cmd` once. It creates **Shadow Screen** shortcuts in the Start Menu and
   on the Desktop.
3. Open **Shadow Screen**. The launcher (`launcher/shadow_screen.py`, run by `pythonw`) serves the
   page on `http://localhost:8765` in the background and opens it as a standalone Chrome/Edge app
   window. Closing the window stops the server.
4. Click **Conectar teclado**, pick the Shadow-S, add GIFs and images, and hit **Enviar**.

The launcher runs on the signed `pythonw.exe` rather than a bundled `.exe`, because Windows
Smart App Control blocks unsigned executables. Any static server on `localhost` (or HTTPS) also
works, since WebHID needs a secure context.

## How it works

The protocol was reverse-engineered by hooking the official tool's HID I/O with Frida. See
[PROTOCOL.md](PROTOCOL.md) for the details. `tools/` contains the Python reference
implementation and the capture scripts.

## Disclaimer

This is an unofficial project with no affiliation to EPOMAKER. It writes to the keyboard's flash
using the same packets the official tool sends. Use it at your own risk.
