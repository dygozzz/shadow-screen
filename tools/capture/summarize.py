"""Summarizes a capture (JSONL from capture.py or JSON from webhid_capture.js).

Collapses runs of packets that start with the same 2 bytes, so a bulk image transfer shows up
as one line ("x4682") between the short command packets around it. Also hints at known pixel
encodings of the test GIF colors.

Usage: python summarize.py log.jsonl
"""
import json
import sys
from collections import Counter

path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    text = f.read().strip()
rows = json.loads(text) if text.startswith("[") else [json.loads(l) for l in text.splitlines() if l]

io = [r for r in rows if r.get("kind") in ("write", "read", "set_output", "set_feature", "get_feature", "get_input")]
if not io:
    sys.exit("No HID I/O in this log. Was the keyboard connected and did the upload run?")
t0 = io[0]["t"]


def data(r):
    # WebHID logs keep the report id apart; prepend it so both formats look alike.
    return (f"{r['reportId']:02x}" if "reportId" in r else "") + r["data"]


print("packets:", len(io), dict(Counter(r["kind"] for r in io)))
print("sizes:", dict(Counter((r["kind"], len(data(r)) // 2) for r in io)))
print("devices:", sorted({r.get("path") or r.get("dev") or "?" for r in io}))
print()

runs = []
for r in io:
    key = (r["kind"], data(r)[:4])
    if runs and runs[-1]["key"] == key:
        runs[-1]["items"].append(r)
    else:
        runs.append({"key": key, "items": [r]})

for i, run in enumerate(runs):
    it = run["items"]
    a, b = it[0], it[-1]
    print(f"[{i}] +{a['t'] - t0}ms {run['key'][0]:<10} x{len(it):<5} {data(a)[:96]}")
    if len(it) > 1:
        print(f"{'':>24}last {data(b)[:96]}")

blob = "".join(data(r) for r in io if r["kind"] in ("write", "set_output", "set_feature"))
print("\nPixel hints (test GIF colors):")
for label, pats in {
    "RGB565 big-endian (red f800, green 07e0, blue 001f)": ["f800f800", "07e007e0", "001f001f"],
    "RGB565 little-endian (red 00f8, green e007, blue 1f00)": ["00f800f8", "e007e007", "1f001f00"],
    "RGB888 (red ff0000, green 00ff00, blue 0000ff)": ["ff0000ff0000", "00ff0000ff00", "0000ff0000ff"],
    "BGR888 (red 0000ff)": ["0000ff0000ff", "00ff0000ff00", "ff0000ff0000"],
}.items():
    hits = [blob.count(p) for p in pats]
    if all(hits):
        print(f"  likely {label}: {hits}")
print("  (no hits for any pattern usually means the image is compressed or encoded differently)")
