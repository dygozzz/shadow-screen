"""Starts a keyboard's official desktop tool with HID hooks and logs its traffic to JSONL.

Usage (from an Administrator terminal if the tool asks for admin):
  python capture.py "C:\\Program Files\\Vendor\\Tool.exe" log.jsonl

This script opens the tool itself: don't start it separately, and close any copy that is
already running first. Child processes are followed too (Electron apps such as EPOMAKER
Driver v4 do their HID work in helper processes).

Do the upload in the tool, then close it (or create a file named STOP next to the log).
"""
import json
import os
import queue
import sys
import time

import frida

HERE = os.path.dirname(os.path.abspath(__file__))
exe, out_path = sys.argv[1], sys.argv[2]
stop_flag = os.path.join(os.path.dirname(os.path.abspath(out_path)), "STOP")
if os.path.exists(stop_flag):
    os.remove(stop_flag)
with open(os.path.join(HERE, "hook.js"), encoding="utf-8") as f:
    HOOK = f.read()

device = frida.get_local_device()
out = open(out_path, "a", encoding="utf-8")
counts = {}
sessions = {}
children = queue.Queue()  # attach outside Frida's callback thread


def on_message(msg, _data):
    if msg["type"] == "send":
        p = msg["payload"]
        out.write(json.dumps(p) + "\n")
        out.flush()
        counts[p["kind"]] = counts.get(p["kind"], 0) + 1
        if p["kind"] in ("open", "close"):
            print(p["kind"], "pid", p.get("pid"), p.get("path"), flush=True)
    else:
        print("script message:", msg, flush=True)


def instrument(pid):
    try:
        session = device.attach(pid)
        session.enable_child_gating()
        script = session.create_script(HOOK)
        script.on("message", on_message)
        script.load()
        sessions[pid] = session
        session.on("detached", lambda reason, crash: sessions.pop(pid, None))
    finally:
        device.resume(pid)


device.on("child-added", lambda child: children.put(child.pid))

# Spawn suspended so the hooks see the device being opened at startup.
main_pid = device.spawn([exe], cwd=os.path.dirname(exe))
print("spawned pid", main_pid, "- use THIS window of the tool", flush=True)
instrument(main_pid)

try:
    while main_pid in sessions and not os.path.exists(stop_flag):
        try:
            pid = children.get(timeout=0.5)
            instrument(pid)
            print("following child pid", pid, flush=True)
        except queue.Empty:
            pass
        except frida.ProcessNotFoundError:
            pass
finally:
    print("stopping | counts:", counts, flush=True)
    if not any(k in counts for k in ("write", "set_output", "set_feature")):
        print("No HID writes were captured. Was the upload done in the window this script opened?")
    out.close()
