# Screen protocols

- [EPOMAKER Shadow-S](#epomaker-shadow-s) (Evision)
- [EPOMAKER RT85](#epomaker-rt85) (Rongyuan)

## EPOMAKER Shadow-S

This was reverse-engineered from *Image Custom Tool* v1.0.0.0 (Evision chip) by hooking
`CreateFileW`, `WriteFile`, `ReadFile` and `DeviceIoControl` with Frida during an upload of a
known test GIF. The packets this project generates are byte-identical to the official ones. The
only exception is the padding between frames, where the official tool sends uninitialized memory
and this project sends zeros.

### Device

| | |
|---|---|
| VID:PID | `320F:5055` (wired Shadow-S) |
| Interface | `MI_03`, usage page `0xFF1C`, usage `0x92` |
| Reports | output report ID `0x04`, 64 bytes; input report ID `0x04`, 8 bytes |
| Screen | 240×135, RGB565 **big-endian**, row-major, top-left first |

Interface `MI_01` (usage page `0xFF60`) is the VIA raw HID channel. Don't confuse the two.

### Packet

Every command is one 64-byte output report:

```
offset 0      report id (0x04)
offset 1..2   checksum: sum of bytes 3..63, uint16 little-endian
offset 3      command
offset 4      payload length
offset 5..7   address, uint24 little-endian
offset 8..63  payload (zero padded)
```

The device answers every packet with one 8-byte input report. For data packets the reply
echoes bytes 0..7 of the request.

### Commands

| Cmd | Name | Notes |
|---|---|---|
| `0x01` | begin | opens a session |
| `0x02` | end | closes or commits a session |
| `0x03` | read info | 4 bytes at `addr`, device info (starts with `aa 55`) |
| `0x05` | read config | `len=1, addr=0` first, then 12 × `len=4` at `addr=0,4,…,44`; data in reply bytes 4..7 |
| `0x06` | write config | `len=0x30, addr=0`, 48-byte config block |
| `0x23` | prepare | erases or prepares flash; the reply takes ~1.4 s |
| `0x21` | data | `len=56` (the last chunk can be shorter), `addr` = byte offset into the image area |

### Config block (48 bytes)

Read it with `0x05` and write it back with `0x06`, changing only these bytes:

| Offset | Meaning |
|---|---|
| 34 | frame count (1–50) |
| 35..41 | clock, BCD: sec, min, hour, weekday (0 = Sunday, not BCD), day, month, year % 100 |
| 43..44 | frame interval in ms, uint16 LE |

### Image layout

Frame `i` lives at address `i * 0x10000`. Each frame is 64800 bytes (240 × 135 × 2) of
big-endian RGB565, padded to 64 KiB. The whole area (`frames × 0x10000` bytes) is sent in
56-byte chunks.

### Upload sequence

```
0x01 begin
0x05 read config (len 1), then 12 × 0x05 len 4   -> base config
0x01 begin
0x06 write config (frame count, clock, interval)
0x02 end
0x23 prepare                                      (wait for the reply, ~1.4 s)
0x21 data × ceil(frames*65536/56)                 (wait for each echo; the official tool sleeps 500 ms after the first)
0x02 end
```

Throughput is about 2 ms per packet, roughly 2.4 s per frame.


## EPOMAKER RT85

Read from the JavaScript of *EPOMAKER Driver v4* 3.2.31, a Rongyuan Electron app. Keyboard class
`yc3123_ss_sn001` with the methods `getTFTLCDDataRGBImg`, `setTFTLCDDataRGBImg`, `___gifToDevice`
and `___pngToDevice`. The app builds the packets in JS and hands them to a local HID service
(gRPC-web on `127.0.0.1:3838`) or to WebHID. Not yet confirmed on real hardware.

### Device

| | |
|---|---|
| VID:PID | `3151:5002` (wired). `3151:5006` is the 2.4G dongle: don't upload through it |
| Interface | `MI_02`, usage page `0xFFFF`, usage `0x02` |
| Reports | feature reports, report ID `0`, 64 bytes, both ways |
| Identity | ~100 Rongyuan keyboards share `3151:5002`. Send `0x8F`; reply bytes 1..4 (uint32 LE) are the firmware id, and RT85 = **2895**. Check it before anything else |
| Screen | 320×172, RGB565 **big-endian**, **column-major** (x outer, y inner) |
| Limits | up to 51 GIF frames (the app's limit for 6 MiB of flash); frame delay is 1 byte (1–255, labelled ms) |

### Packet

64 bytes, with a checksum at byte 7: `0xFF - (sum(bytes 0..6) & 0xFF)`.

### Upload

```
0xA5 header  [A5, frame, N, delay, len&FF, (len>>8)&FF, 0, ck,
              left, top, right, bottom (low bytes), left, top, right, bottom (high bytes),
              (len>>16)&FF, (len>>24)&FF, gif_layer]
             len = bytes of ONE frame; right/bottom exclusive; read the feature report after
             ~100 ms, where reply[1] == 1 means OK (the app retries up to 10 times)
0x25 data    [25, frame, N, delay, idx&FF, idx>>8, n (<=56), ck, 56 data bytes]
             idx restarts at 0 for each frame; 2 ms between packets; no reply
```

- **GIF:** one header with `frame=0, N=frames, delay`, then the data of frame 0..N-1.
- **Still image:** header and data with `frame=slot (0..4), N=1, delay=0`.
- No end or commit command.
- This project always sends the full box (0, 0, 320, 172), so `len` = 110080 and there are 1966
  packets per frame.

### Never send

The same firmware has destructive commands. `launcher/models/rt85.py` refuses everything except
`0x8F`, `0xA5` and `0x25`:

- bootloader: `7F`, `F8`, `30`/`31`/`B1`, `43`/`44`/`C3`/`C4`
- firmware upgrade: `BA`
- raw screen-flash writes: `32`/`B2`
- full flash erase: `AC`
- reset: `01`
