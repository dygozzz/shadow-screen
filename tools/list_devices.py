"""Lists HID interfaces of EPOMAKER-like keyboards (or every device with --all).

Vendor-defined interfaces (usage page 0xFF00-0xFFFF) are where screen/config protocols live.
"""
import sys

import hid

show_all = "--all" in sys.argv
rows = []
for d in hid.enumerate():
    name = (d.get("product_string") or "").strip()
    maker = (d.get("manufacturer_string") or "").strip()
    if not show_all and "epomaker" not in (name + maker).lower() and d["vendor_id"] != 0x320F:
        continue
    rows.append(d)

if not rows:
    print("Nenhum teclado EPOMAKER encontrado. Use --all para listar tudo.")
for d in sorted(rows, key=lambda d: (d["vendor_id"], d["product_id"], d["interface_number"], d["usage_page"])):
    vendor_defined = d["usage_page"] >= 0xFF00
    print(f"{d['vendor_id']:04X}:{d['product_id']:04X}  interface {d['interface_number']:<2}  "
          f"usage_page 0x{d['usage_page']:04X}  usage 0x{d['usage']:02X}  "
          f"{(d.get('product_string') or '').strip()}{'   <-- vendor-defined' if vendor_defined else ''}")
