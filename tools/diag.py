"""Shadow Screen diagnostics: checks the setup, inspects the keyboard and the official tool,
optionally records an upload, and bundles everything into one zip to send for analysis.

Normally started by DIAGNOSTICO.cmd (repo root), which prepares Python and the packages.
Usage: python tools/diag.py [--pip-log FILE] [--out DIR]
"""
import argparse
import ctypes
import datetime
import glob
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import traceback

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
CODE_EXT = {".js", ".mjs", ".cjs", ".html", ".json", ".wasm", ".css", ".map", ".txt", ".node"}
MAX_CODE_FILE = 20 * 1024 * 1024


# ---------- output: console + log file ----------
class Log:
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8")

    def __call__(self, *parts):
        line = " ".join(str(p) for p in parts)
        print(line, flush=True)
        self.f.write(line + "\n")
        self.f.flush()

    def section(self, title):
        self("")
        self("=" * 70)
        self(title)
        self("=" * 70)


def desktop_dir():
    buf = ctypes.create_unicode_buffer(260)
    if ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf) == 0:  # CSIDL_DESKTOPDIRECTORY
        return buf.value
    return os.path.join(os.path.expanduser("~"), "Desktop")


def ask(prompt, default=""):
    try:
        ans = input(prompt).strip()
    except EOFError:
        ans = ""
    return ans or default


def run(cmd, log, **kw):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, **kw)
        out = (r.stdout + r.stderr).strip()
        log(f"$ {' '.join(cmd)}  (exit {r.returncode})")
        if out:
            log(out)
        return r
    except Exception as e:
        log(f"$ {' '.join(cmd)}  -> {e}")
        return None


# ---------- checks ----------
def check_system(log):
    log.section("1. Sistema")
    log("Windows:", platform.platform())
    log("Python:", sys.version.replace("\n", " "), "|", sys.executable)
    log("Administrador:", bool(ctypes.windll.shell32.IsUserAnAdmin()))
    log("Pasta do projeto:", ROOT)
    git = shutil.which("git")
    if git:
        run([git, "-C", ROOT, "log", "--oneline", "-1"], log)
        run([git, "-C", ROOT, "status", "--short"], log)
    else:
        log("git: não encontrado")
    sac = run(["reg", "query", r"HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy", "/v", "VerifiedAndReputablePolicyState"], log)
    if sac is None or sac.returncode != 0:
        log("(Smart App Control: não deu para ler, sem problema)")


def check_packages(log, pip_log):
    log.section("2. Pacotes Python")
    if pip_log and os.path.exists(pip_log):
        with open(pip_log, encoding="utf-8", errors="replace") as f:
            text = f.read().strip()
        log("Saída do pip install:")
        log(text or "(vazia: tudo instalado sem mensagens)")
    ok = True
    try:
        import hid
        kind = "hidapi (correto)" if hasattr(hid, "device") else "PACOTE ERRADO (pip uninstall hid; pip install hidapi)"
        log("hid:", getattr(hid, "__file__", "?"), "->", kind)
        ok &= hasattr(hid, "device")
    except Exception as e:
        log("hid: ERRO ->", repr(e))
        ok = False
    try:
        import frida
        log("frida:", frida.__version__)
    except Exception as e:
        log("frida: ERRO ->", repr(e))
        ok = False
    try:
        import PIL
        log("pillow:", PIL.__version__)
    except Exception as e:
        log("pillow: ERRO ->", repr(e))
        ok = False
    return ok


def check_devices(log, bundle):
    log.section("3. Dispositivos HID (teclados e tudo o que estiver plugado)")
    import hid

    devs = hid.enumerate()
    rows = []
    for d in devs:
        rows.append({k: (v.decode(errors="replace") if isinstance(v, bytes) else v) for k, v in d.items()})
    with open(os.path.join(bundle, "hid_devices.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=1, default=str)

    by_id = {}
    for d in rows:
        by_id.setdefault((d["vendor_id"], d["product_id"]), []).append(d)
    keyboards = []
    for (vid, pid), ifaces in sorted(by_id.items()):
        names = {f"{(d.get('manufacturer_string') or '').strip()} {(d.get('product_string') or '').strip()}".strip() for d in ifaces}
        text = " ".join(names).lower()
        is_kb = "keyboard" in text or "epomaker" in text or any((d["usage_page"], d["usage"]) == (1, 6) for d in ifaces)
        if is_kb:
            keyboards.append((vid, pid, names))
        log(f"\n{vid:04X}:{pid:04X}  {' / '.join(sorted(n for n in names if n))}{'   [TECLADO]' if is_kb else ''}")
        for d in sorted(ifaces, key=lambda d: (d["interface_number"], d["usage_page"], d["usage"])):
            tag = "   <-- vendor-defined" if d["usage_page"] >= 0xFF00 else ""
            log(f"    interface {d['interface_number']:<2}  usage_page 0x{d['usage_page']:04X}  usage 0x{d['usage']:02X}{tag}")
    log("\nTeclados encontrados:", ", ".join(f"{v:04X}:{p:04X} {sorted(n)}" for v, p, n in keyboards) or "NENHUM")
    if not keyboards:
        log("!! Nenhum teclado reconhecido. Confira se ele está ligado POR CABO USB.")


def find_driver(log):
    log.section("4. Programa oficial (EPOMAKER Driver)")
    roots = [os.path.expandvars(p) for p in (r"%LOCALAPPDATA%\Programs", r"%ProgramFiles%", r"%ProgramFiles(x86)%")]
    candidates = []
    for root in roots:
        for d in glob.glob(os.path.join(root, "*")):
            if "epomaker" in os.path.basename(d).lower() and os.path.isdir(d):
                for exe in glob.glob(os.path.join(d, "*.exe")):
                    if "uninst" not in os.path.basename(exe).lower():
                        candidates.append(exe)
    for c in candidates:
        log("encontrado:", c)
    if not candidates:
        log("Nenhum programa EPOMAKER encontrado nas pastas padrão.")
        manual = ask("Se souber o caminho do .exe do programa oficial, cole aqui (ou Enter para pular): ")
        if manual and os.path.isfile(manual.strip('"')):
            candidates.append(manual.strip('"'))
    exe = next((c for c in candidates if "driver" in os.path.basename(c).lower()), candidates[0] if candidates else None)
    if exe:
        log("usando:", exe)
    r = run(["tasklist", "/FO", "CSV", "/NH"], lambda *a: None)
    if r and exe:
        name = os.path.basename(exe).lower()
        running = [l for l in r.stdout.splitlines() if l.lower().startswith(f'"{name}"')]
        log(f"cópias rodando agora de {os.path.basename(exe)}: {len(running)}")
    return exe


def bundle_driver_code(log, exe, bundle):
    log.section("5. Código do programa oficial")
    if not exe:
        log("Pulado (programa não encontrado).")
        return
    res = os.path.join(os.path.dirname(exe), "resources")
    if not os.path.isdir(res):
        log("Sem pasta resources (não é um app Electron):", res)
        return
    for name in sorted(os.listdir(res)):
        p = os.path.join(res, name)
        size = sum(os.path.getsize(os.path.join(a, f)) for a, _, fs in os.walk(p) for f in fs) if os.path.isdir(p) else os.path.getsize(p)
        log(f"  resources\\{name}  ({size / 1024 / 1024:.1f} MB)")
    natives = [os.path.join(a, f) for a, _, fs in os.walk(res) for f in fs if f.endswith((".node", ".wasm"))]
    log("Módulos nativos/wasm:", *(["\n  " + n for n in natives] or ["nenhum"]))

    dest = os.path.join(bundle, "driver_code")
    copied = skipped = 0
    for src_root in (os.path.join(res, "app"), os.path.join(res, "app.asar.unpacked")):
        if not os.path.isdir(src_root):
            continue
        for a, dirs, fs in os.walk(src_root):
            dirs[:] = [d for d in dirs if d != "node_modules"] if a == src_root else dirs
            for f in fs:
                src = os.path.join(a, f)
                if os.path.splitext(f)[1].lower() not in CODE_EXT or os.path.getsize(src) > MAX_CODE_FILE:
                    skipped += 1
                    continue
                rel = os.path.relpath(src, res)
                os.makedirs(os.path.dirname(os.path.join(dest, rel)), exist_ok=True)
                shutil.copy2(src, os.path.join(dest, rel))
                copied += 1
    asar = os.path.join(res, "app.asar")
    if os.path.isfile(asar) and os.path.getsize(asar) < 150 * 1024 * 1024:
        os.makedirs(dest, exist_ok=True)
        shutil.copy2(asar, os.path.join(dest, "app.asar"))
        copied += 1
    pkg = os.path.join(res, "app", "node_modules")
    if os.path.isdir(pkg):
        log("node_modules:", ", ".join(sorted(os.listdir(pkg))[:80]))
    log(f"Copiados {copied} arquivos de código ({skipped} ignorados: imagens/mídia/grandes).")


def capture(log, exe, bundle):
    log.section("6. Gravação do envio de um GIF")
    if not exe:
        log("Pulado (programa não encontrado).")
        return
    if ask("Quer gravar o envio de um GIF agora? [s/N] ").lower() not in ("s", "sim", "y"):
        log("Pulado pelo usuário.")
        return
    res = ask("Resolução da tela do teclado, ex.: 240x135 (Enter = 240x135): ", "240x135").lower().replace(" ", "")
    try:
        w, h = (int(x) for x in res.split("x"))
    except ValueError:
        w, h = 240, 135
    gif = os.path.join(desktop_dir(), "teste.gif")
    run([sys.executable, os.path.join(TOOLS, "capture", "make_test_gif.py"), gif, str(w), str(h)], log)
    shutil.copy2(gif, bundle)

    print()
    print(">>> 1. Abra o EPOMAKER Driver NORMALMENTE (pelo atalho de sempre) e deixe a janela aberta.")
    ask(">>>    Quando ele estiver aberto, aperte Enter aqui...")
    logfile = os.path.join(bundle, "capture.jsonl")
    cmd = [sys.executable, os.path.join(TOOLS, "capture", "capture.py"), "--attach", os.path.basename(exe), logfile]
    log("$", " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    threading.Thread(target=lambda: [log("   [captura]", l.rstrip()) for l in proc.stdout], daemon=True).start()
    time.sleep(4)
    if proc.poll() is not None:
        log("!! A gravação não conseguiu se conectar. Se apareceu 'access denied', rode o DIAGNOSTICO.cmd como administrador.")
        return
    print()
    print(f">>> 2. No Driver, envie o arquivo teste.gif (está na Área de Trabalho, {w}x{h}) para o teclado.")
    print(">>>    Anote o intervalo/velocidade que estiver configurado.")
    print(">>> 3. Confira que o GIF apareceu na tela do teclado (vermelho, verde, azul, metade branco/preto).")
    ask(">>>    Quando terminar, aperte Enter aqui...")
    log("Intervalo informado:", ask(">>> Qual intervalo/velocidade estava configurado? (Enter se não souber): ", "?"))
    open(os.path.join(bundle, "STOP"), "w").close()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
    time.sleep(1)
    if os.path.exists(logfile):
        run([sys.executable, os.path.join(TOOLS, "capture", "summarize.py"), logfile], log)
    else:
        log("!! Nenhum arquivo de gravação foi criado.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pip-log")
    ap.add_argument("--out")
    args = ap.parse_args()

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    out_dir = args.out or os.environ.get("SS_DIAG_OUT") or desktop_dir()
    bundle = os.path.join(out_dir, f"ShadowScreen-diagnostico-{stamp}")
    os.makedirs(bundle, exist_ok=True)
    log = Log(os.path.join(bundle, "log.txt"))
    log("Shadow Screen - diagnóstico", datetime.datetime.now().isoformat(timespec="seconds"))

    steps_ok = True
    try:
        check_system(log)
        if check_packages(log, args.pip_log):
            check_devices(log, bundle)
            exe = find_driver(log)
            bundle_driver_code(log, exe, bundle)
            capture(log, exe, bundle)
        else:
            steps_ok = False
            log("\n!! Faltam pacotes, então parei aqui. Mande este log mesmo assim.")
    except Exception:
        steps_ok = False
        log("\n!! ERRO inesperado:")
        log(traceback.format_exc())

    stop = os.path.join(bundle, "STOP")
    if os.path.exists(stop):
        os.remove(stop)
    log.f.close()
    zip_path = shutil.make_archive(bundle, "zip", bundle)
    print()
    print("#" * 70)
    print("PRONTO" if steps_ok else "TERMINOU COM PROBLEMAS (normal, o log explica)")
    print("Mande ESTE arquivo:", zip_path)
    print("#" * 70)
    subprocess.run(["explorer", "/select,", zip_path])


if __name__ == "__main__":
    main()
