"""Decode capture: header = [04][sum16 LE][cmd][len][addr24 LE]; print non-bulk packets and bulk write ranges."""
import json
import sys

rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
io = [r for r in rows if r["kind"] in ("write", "read")]
t0 = io[0]["t"]

bad_sum = 0
pairs = []
for i in range(0, len(io) - 1):
    w = io[i]
    if w["kind"] != "write":
        continue
    b = bytes.fromhex(w["data"])
    s = sum(b[3:]) & 0xFFFF
    if s != b[1] | (b[2] << 8):
        bad_sum += 1
    rd = io[i + 1]["data"] if io[i + 1]["kind"] == "read" else None
    pairs.append((w["t"] - t0, b, rd))
print("writes:", len(pairs), "checksum mismatches:", bad_sum)

cur = None
for t, b, rd in pairs:
    cmd, ln, addr = b[3], b[4], b[5] | (b[6] << 8) | (b[7] << 16)
    if cmd == 0x21:
        data = b[8 : 8 + ln]
        if cur and cur["end"] == addr:
            cur["end"] = addr + ln
            cur["n"] += 1
            cur["t1"] = t
            cur["vals"].add(data[:2].hex())
            continue
        if cur:
            print(f"  BULK 0x21 addr {cur['start']:#08x}-{cur['end']:#08x} ({cur['end'] - cur['start']} B, {cur['n']} pkts) t={cur['t0']}..{cur['t1']}ms first-pixels={sorted(cur['vals'])[:6]}")
        cur = {"start": addr, "end": addr + ln, "n": 1, "t0": t, "t1": t, "vals": {data[:2].hex()}}
        continue
    if cur:
        print(f"  BULK 0x21 addr {cur['start']:#08x}-{cur['end']:#08x} ({cur['end'] - cur['start']} B, {cur['n']} pkts) t={cur['t0']}..{cur['t1']}ms first-pixels={sorted(cur['vals'])[:6]}")
        cur = None
    print(f"t={t:>6}ms cmd={cmd:#04x} len={ln:#04x} addr={addr:#08x} payload={b[8:8 + max(ln, 8)].hex()} -> {rd}")
if cur:
    print(f"  BULK 0x21 addr {cur['start']:#08x}-{cur['end']:#08x} ({cur['end'] - cur['start']} B, {cur['n']} pkts) t={cur['t0']}..{cur['t1']}ms first-pixels={sorted(cur['vals'])[:6]}")
