// Records WebHID traffic of a keyboard's official *web* tool (Chrome/Edge).
//
// 1. Open the official site, press F12 -> Console.
// 2. Paste this whole file and press Enter, BEFORE connecting the keyboard on the site.
// 3. Connect the keyboard on the site and upload the test GIF.
// 4. Run:  copy(JSON.stringify(window.__hidlog))  and paste the result into a file log.json
//
// Output format matches what tools/capture/summarize.py expects.
(() => {
  window.__hidlog = [];
  const hex = v => {
    const b = v instanceof DataView ? new Uint8Array(v.buffer, v.byteOffset, v.byteLength)
      : ArrayBuffer.isView(v) ? new Uint8Array(v.buffer, v.byteOffset, v.byteLength)
      : new Uint8Array(v);
    return Array.from(b, x => x.toString(16).padStart(2, "0")).join("");
  };
  const dev = d => `${d.vendorId.toString(16).padStart(4, "0")}:${d.productId.toString(16).padStart(4, "0")}`;
  const log = (kind, d, reportId, data) =>
    window.__hidlog.push({ t: Date.now(), kind, dev: dev(d), reportId, data: hex(data) });

  const P = HIDDevice.prototype;
  const sendReport = P.sendReport, sendFeature = P.sendFeatureReport, recvFeature = P.receiveFeatureReport;
  P.sendReport = function (id, data) { log("write", this, id, data); return sendReport.call(this, id, data); };
  P.sendFeatureReport = function (id, data) { log("set_feature", this, id, data); return sendFeature.call(this, id, data); };
  P.receiveFeatureReport = async function (id) {
    const r = await recvFeature.call(this, id);
    log("get_feature", this, id, r);
    return r;
  };

  // Input reports, whether the site uses addEventListener or the oninputreport property.
  const add = P.addEventListener;
  P.addEventListener = function (type, fn, opts) {
    if (type === "inputreport") {
      const wrapped = e => { log("read", this, e.reportId, e.data); return fn.call(this, e); };
      return add.call(this, type, wrapped, opts);
    }
    return add.call(this, type, fn, opts);
  };
  const desc = Object.getOwnPropertyDescriptor(P, "oninputreport");
  if (desc && desc.set) {
    Object.defineProperty(P, "oninputreport", {
      configurable: true, get: desc.get,
      set(fn) { desc.set.call(this, fn && (e => { log("read", this, e.reportId, e.data); return fn.call(this, e); })); },
    });
  }
  console.log("HID capture on. After the upload run: copy(JSON.stringify(window.__hidlog))");
})();
