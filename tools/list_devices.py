"""Lists the HID interfaces of plugged-in keyboards (or every HID device with --all).

A device is shown when any of its interfaces looks like a keyboard or mentions EPOMAKER, and
then ALL of its interfaces are listed. Vendor-defined interfaces (usage page 0xFF00-0xFFFF) are
where screen/config protocols live.
"""
import sys
from collections import defaultdict

import hid

show_all = "--all" in sys.argv
by_id = defaultdict(list)
for d in hid.enumerate():
    by_id[(d["vendor_id"], d["product_id"])].append(d)


def interesting(ifaces):
    for d in ifaces:
        text = f"{d.get('product_string') or ''} {d.get('manufacturer_string') or ''}".lower()
        if "epomaker" in text or "keyboard" in text or (d["usage_page"], d["usage"]) == (0x01, 0x06):
            return True
    return False


shown = 0
for (vid, pid), ifaces in sorted(by_id.items()):
    if not show_all and not interesting(ifaces):
        continue
    shown += 1
    names = {(d.get("manufacturer_string") or "").strip() + " " + (d.get("product_string") or "").strip() for d in ifaces}
    print(f"\n{vid:04X}:{pid:04X}  {' / '.join(sorted(n.strip() for n in names if n.strip()))}")
    for d in sorted(ifaces, key=lambda d: (d["interface_number"], d["usage_page"], d["usage"])):
        tag = "   <-- vendor-defined" if d["usage_page"] >= 0xFF00 else ""
        print(f"    interface {d['interface_number']:<2}  usage_page 0x{d['usage_page']:04X}  usage 0x{d['usage']:02X}{tag}")

if not shown:
    print("Nenhum teclado encontrado. Use --all para listar todos os dispositivos HID.")
