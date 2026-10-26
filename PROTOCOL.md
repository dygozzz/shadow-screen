# EPOMAKER Shadow-S screen protocol

This was reverse-engineered from *Image Custom Tool* v1.0.0.0 (Evision chip) by hooking
`CreateFileW`, `WriteFile`, `ReadFile` and `DeviceIoControl` with Frida during an upload of a
known test GIF. The packets this project generates are byte-identical to the official ones. The
only exception is the padding between frames, where the official tool sends uninitialized memory
and this project sends zeros.

## Device

| | |
|---|---|
| VID:PID | `320F:5055` (wired Shadow-S) |
| Interface | `MI_03`, usage page `0xFF1C`, usage `0x92` |
| Reports | output report ID `0x04`, 64 bytes; input report ID `0x04`, 8 bytes |
| Screen | 240×135, RGB565 **big-endian**, row-major, top-left first |

Interface `MI_01` (usage page `0xFF60`) is the VIA raw HID channel. Don't confuse the two.

## Packet

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

## Commands

| Cmd | Name | Notes |
|---|---|---|
| `0x01` | begin | opens a session |
| `0x02` | end | closes or commits a session |
| `0x03` | read info | 4 bytes at `addr`, device info (starts with `aa 55`) |
| `0x05` | read config | `len=1, addr=0` first, then 12 × `len=4` at `addr=0,4,…,44`; data in reply bytes 4..7 |
| `0x06` | write config | `len=0x30, addr=0`, 48-byte config block |
| `0x23` | prepare | erases or prepares flash; the reply takes ~1.4 s |
| `0x21` | data | `len=56` (the last chunk can be shorter), `addr` = byte offset into the image area |

## Config block (48 bytes)

Read it with `0x05` and write it back with `0x06`, changing only these bytes:

| Offset | Meaning |
|---|---|
| 34 | frame count (1–50) |
| 35..41 | clock, BCD: sec, min, hour, weekday (0 = Sunday, not BCD), day, month, year % 100 |
| 43..44 | frame interval in ms, uint16 LE |

## Image layout

Frame `i` lives at address `i * 0x10000`. Each frame is 64800 bytes (240 × 135 × 2) of
big-endian RGB565, padded to 64 KiB. The whole area (`frames × 0x10000` bytes) is sent in
56-byte chunks.

## Upload sequence

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
