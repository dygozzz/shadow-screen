"""Attach to Image Custom Tool and log its HID traffic to a JSONL file.

Usage: python capture.py <out.jsonl>
Spawns the tool itself. Stops when the target exits or when a file named STOP appears next to the log.
"""
import json
import os
import sys
import time

import frida

TARGET = "Image Custom Tool.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
out_path = sys.argv[1]
stop_flag = os.path.join(os.path.dirname(os.path.abspath(out_path)), "STOP")
if os.path.exists(stop_flag):
    os.remove(stop_flag)

INSTALL_DIR = r"C:\Program Files (x86)\Image Custom Tool"
# Spawn suspended so the hooks see the device being opened at startup.
pid = frida.spawn([os.path.join(INSTALL_DIR, TARGET)], cwd=INSTALL_DIR)
session = frida.attach(pid)
print("spawned pid", pid, flush=True)

counts = {}
out = open(out_path, "a", encoding="utf-8")
detached = []


def on_message(msg, _data):
    if msg["type"] == "send":
        p = msg["payload"]
        out.write(json.dumps(p) + "\n")
        out.flush()
        counts[p["kind"]] = counts.get(p["kind"], 0) + 1
        if p["kind"] in ("ready", "open", "close"):
            print(p, flush=True)
    else:
        print("script message:", msg, flush=True)


session.on("detached", lambda reason, crash: detached.append(reason))
with open(os.path.join(HERE, "hook.js"), encoding="utf-8") as f:
    script = session.create_script(f.read())
script.on("message", on_message)
script.load()
frida.resume(pid)

try:
    while not detached and not os.path.exists(stop_flag):
        time.sleep(0.5)
finally:
    print("stopping:", detached or "STOP flag", "| counts:", counts, flush=True)
    out.close()
