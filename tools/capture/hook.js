// Logs the HID I/O a keyboard's official tool does (WriteFile/ReadFile/DeviceIoControl/HidD_*).
const handles = {};          // handle -> device path (only for HID paths)
const pendingReads = {};     // overlapped ptr -> {h, buf}
const unknownDev = {};       // handle -> true/false: device handle opened before we attached?

function mod(name) {
  return Process.findModuleByName(name);
}
function exp(m, name) {
  const mm = mod(m);
  return mm ? mm.findExportByName(name) : null;
}
function hex(ptr, len) {
  if (ptr.isNull() || len <= 0) return '';
  const b = new Uint8Array(ptr.readByteArray(len));
  let s = '';
  for (let i = 0; i < b.length; i++) s += (b[i] < 16 ? '0' : '') + b[i].toString(16);
  return s;
}
function emit(kind, h, data, extra) {
  send(Object.assign({ t: Date.now(), pid: Process.id, kind: kind, h: h, path: handles[h] || null, data: data }, extra || {}));
}

// Handles opened before the hooks (e.g. with --attach) have no known path. Device handles report
// FILE_TYPE_UNKNOWN (0); files, pipes and consoles don't, so treat those 0s as devices.
const getFileType = new NativeFunction(exp('kernelbase.dll', 'GetFileType') || exp('kernel32.dll', 'GetFileType'), 'uint32', ['pointer']);
function isDevice(h) {
  if (handles[h]) return true;
  if (unknownDev[h] === undefined) unknownDev[h] = getFileType(ptr(h)) === 0;
  return unknownDev[h];
}

const createFileW = exp('kernelbase.dll', 'CreateFileW') || exp('kernel32.dll', 'CreateFileW');
Interceptor.attach(createFileW, {
  onEnter(args) { this.path = args[0].isNull() ? '' : args[0].readUtf16String(); },
  onLeave(ret) {
    if (this.path && /hid#|vid_/i.test(this.path)) {
      handles[ret.toString()] = this.path;
      send({ t: Date.now(), pid: Process.id, kind: 'open', h: ret.toString(), path: this.path });
    }
  }
});

const closeHandle = exp('kernelbase.dll', 'CloseHandle') || exp('kernel32.dll', 'CloseHandle');
Interceptor.attach(closeHandle, {
  onEnter(args) {
    const h = args[0].toString();
    delete unknownDev[h];
    if (handles[h]) { send({ t: Date.now(), pid: Process.id, kind: 'close', h: h, path: handles[h] }); delete handles[h]; }
  }
});

const writeFile = exp('kernelbase.dll', 'WriteFile') || exp('kernel32.dll', 'WriteFile');
Interceptor.attach(writeFile, {
  onEnter(args) {
    const h = args[0].toString();
    if (isDevice(h)) emit('write', h, hex(args[1], args[2].toInt32()));
  }
});

const readFile = exp('kernelbase.dll', 'ReadFile') || exp('kernel32.dll', 'ReadFile');
Interceptor.attach(readFile, {
  onEnter(args) {
    this.h = args[0].toString();
    this.buf = args[1]; this.len = args[2].toInt32(); this.nread = args[3]; this.ov = args[4];
  },
  onLeave(ret) {
    if (!isDevice(this.h)) return;
    if (ret.toInt32() !== 0) {
      const n = this.nread.isNull() ? this.len : this.nread.readU32();
      emit('read', this.h, hex(this.buf, n));
    } else if (!this.ov.isNull()) {
      pendingReads[this.ov.toString()] = { h: this.h, buf: this.buf, len: this.len };
    }
  }
});

const getOv = exp('kernelbase.dll', 'GetOverlappedResult') || exp('kernel32.dll', 'GetOverlappedResult');
Interceptor.attach(getOv, {
  onEnter(args) { this.ov = args[1].toString(); this.n = args[2]; },
  onLeave(ret) {
    const p = pendingReads[this.ov];
    if (p && ret.toInt32() !== 0) {
      const n = this.n.isNull() ? p.len : this.n.readU32();
      emit('read', p.h, hex(p.buf, n));
      delete pendingReads[this.ov];
    }
  }
});

const ioctl = exp('kernelbase.dll', 'DeviceIoControl') || exp('kernel32.dll', 'DeviceIoControl');
Interceptor.attach(ioctl, {
  onEnter(args) {
    this.h = args[0].toString();
    if (!handles[this.h]) return;
    this.code = args[1].toUInt32();
    this.out = args[4]; this.outLen = args[5].toInt32(); this.ret = args[6];
    emit('ioctl_in', this.h, hex(args[2], args[3].toInt32()), { code: '0x' + this.code.toString(16) });
  },
  onLeave(r) {
    if (!handles[this.h]) return;
    const n = this.ret.isNull() ? this.outLen : this.ret.readU32();
    emit('ioctl_out', this.h, hex(this.out, Math.min(n, this.outLen)), { code: '0x' + this.code.toString(16), ok: r.toInt32() });
  }
});

// hid.dll helpers (Set/GetFeature, Set/GetInputReport, SetOutputReport). hid.dll is often loaded
// lazily (e.g. by Electron apps), so hook it whenever it shows up.
let hidHooked = false;
function hookHid() {
  if (hidHooked || !mod('hid.dll')) return;
  hidHooked = true;
  [['HidD_SetOutputReport', 'set_output'], ['HidD_SetFeature', 'set_feature']].forEach(([fn, kind]) => {
    const a = exp('hid.dll', fn);
    if (a) Interceptor.attach(a, {
      onEnter(args) { this.h = args[0].toString(); this.d = hex(args[1], args[2].toInt32()); },
      onLeave(r) { emit(kind, this.h, this.d, { ok: r.toInt32() }); }
    });
  });
  [['HidD_GetFeature', 'get_feature'], ['HidD_GetInputReport', 'get_input']].forEach(([fn, kind]) => {
    const a = exp('hid.dll', fn);
    if (a) Interceptor.attach(a, {
      onEnter(args) { this.h = args[0].toString(); this.b = args[1]; this.l = args[2].toInt32(); },
      onLeave(r) { emit(kind, this.h, hex(this.b, this.l), { ok: r.toInt32() }); }
    });
  });
}
hookHid();
if (typeof Process.attachModuleObserver === 'function') {
  Process.attachModuleObserver({ onAdded(m) { if (m.name.toLowerCase() === 'hid.dll') hookHid(); } });
}

send({ t: Date.now(), pid: Process.id, kind: 'ready', arch: Process.arch });
