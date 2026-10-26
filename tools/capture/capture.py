"""Records the HID traffic of a keyboard's official desktop tool to JSONL.

Two ways to run it (from an Administrator terminal if the tool asks for admin):

  python capture.py "C:\\...\\Tool.exe" log.jsonl
      Opens the tool itself with the hooks in place. Close every copy of the tool first
      (including the tray icon) and don't open it separately.

  python capture.py --attach "Tool.exe" log.jsonl
      Hooks a copy that is ALREADY running (every process with that name). Use this when the
      first mode records nothing, e.g. tools that stay in the tray or relaunch themselves.

Child processes are followed too (Electron apps such as EPOMAKER Driver v4 do their HID work in
helper processes). Do the upload in the tool, then close it (or create a file named STOP next to
the log). The script prints what it sees while it runs.
"""
import json
import os
import queue
import sys
import time

import frida

HERE = os.path.dirname(os.path.abspath(__file__))
attach_mode = sys.argv[1] == "--attach"
target, out_path = (sys.argv[2], sys.argv[3]) if attach_mode else (sys.argv[1], sys.argv[2])
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
WRITE_KINDS = ("write", "set_output", "set_feature")


def on_message(msg, _data):
    if msg["type"] != "send":
        print("script message:", msg, flush=True)
        return
    p = msg["payload"]
    out.write(json.dumps(p) + "\n")
    out.flush()
    kind = p["kind"]
    counts[kind] = counts.get(kind, 0) + 1
    if kind in ("open", "close"):
        print(kind, "pid", p.get("pid"), p.get("path"), flush=True)
    elif kind in WRITE_KINDS:
        n = sum(counts.get(k, 0) for k in WRITE_KINDS)
        if n == 1 or n % 500 == 0:
            print(f"capturing: {n} packets sent to devices so far (pid {p.get('pid')})", flush=True)


def instrument(pid, resume):
    try:
        session = device.attach(pid)
        session.enable_child_gating()
        script = session.create_script(HOOK)
        script.on("message", on_message)
        script.load()
        sessions[pid] = session
        session.on("detached", lambda reason, crash: sessions.pop(pid, None))
    finally:
        if resume:
            device.resume(pid)


device.on("child-added", lambda child: children.put(child.pid))

if attach_mode:
    me = {os.getpid(), os.getppid()}
    pids = [p.pid for p in device.enumerate_processes()
            if p.name.lower() == os.path.basename(target).lower() and p.pid not in me]
    if not pids:
        sys.exit(f'No running process named "{os.path.basename(target)}". Open the tool first.')
    for pid in pids:
        try:
            instrument(pid, resume=False)
        except frida.ProcessNotFoundError:
            pass
    print(f"attached to {len(sessions)} process(es): {sorted(sessions)}. Do the upload now.", flush=True)
else:
    pid = device.spawn([target], cwd=os.path.dirname(target))
    print("opened the tool, pid", pid, "- use THIS window of the tool", flush=True)
    instrument(pid, resume=True)
started = time.time()

try:
    while sessions and not os.path.exists(stop_flag):
        try:
            pid = children.get(timeout=0.5)
            instrument(pid, resume=True)
            print("following child pid", pid, flush=True)
        except queue.Empty:
            pass
        except frida.ProcessNotFoundError:
            pass
finally:
    print("stopping | counts:", counts, flush=True)
    if not any(k in counts for k in WRITE_KINDS):
        if not attach_mode and time.time() - started < 10:
            print("The tool closed right away: another copy is probably running (check the tray /"
                  " Task Manager). Close it, or open the tool normally and use --attach.")
        else:
            print("No packets to devices were captured. Was the upload done in the hooked window?"
                  " Try --attach with the tool already open.")
    out.close()
