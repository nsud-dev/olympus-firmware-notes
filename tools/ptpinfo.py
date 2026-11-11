#!/usr/bin/env python3
"""Ask an Olympus camera in USB PTP mode what it supports (PTP GetDeviceInfo).

Needs: brew install libusb ; python3 -m pip install pyusb
Run:   killall -9 ptpcamerad; python3 ptpinfo.py
"""
import struct, sys
import usb.core, usb.util

dev = usb.core.find(idVendor=0x07b4)
if dev is None:
    sys.exit('No Olympus USB device found')
print(f'device {dev.idVendor:04x}:{dev.idProduct:04x}')
try:
    if dev.is_kernel_driver_active(0):
        dev.detach_kernel_driver(0)
except Exception:
    pass
dev.set_configuration
intf = dev.get_active_configuration[(0, 0)]
print(f'interface class {intf.bInterfaceClass:02x}/{intf.bInterfaceSubClass:02x}/{intf.bInterfaceProtocol:02x}')
usb.util.claim_interface(dev, intf)
ep_out = usb.util.find_descriptor(intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT and usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK)
ep_in = usb.util.find_descriptor(intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN and usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK)

tid = 0
def op(code, *params):
    global tid
    tid += 1
    ep_out.write(struct.pack('<IHHI', 12 + 4 * len(params), 1, code, tid) + b''.join(struct.pack('<I', p) for p in params))
    data = b''
    while True:
        buf = bytes(ep_in.read(0x10000, timeout=5000))
        ln, typ, rc, _ = struct.unpack_from('<IHHI', buf)
        while len(buf) < ln:
            buf += bytes(ep_in.read(0x10000, timeout=5000))
        if typ == 2:
            data += buf[12:ln]
        elif typ == 3:
            return rc, data

def u16arr(b, o):
    n, = struct.unpack_from('<I', b, o); o += 4
    return list(struct.unpack_from(f'<{n}H', b, o)), o + 2 * n
def pstr(b, o):
    n = b[o]; o += 1
    return b[o:o + 2 * n].decode('utf-16-le', 'replace').rstrip('\0'), o + 2 * n

rc, d = op(0x1001)
print(f'GetDeviceInfo response 0x{rc:04x}, {len(d)} bytes')
o = 0
std, vid, vver = struct.unpack_from('<HIH', d, o); o += 8
ext, o = pstr(d, o)
fmode, = struct.unpack_from('<H', d, o); o += 2
ops, o = u16arr(d, o); evs, o = u16arr(d, o); props, o = u16arr(d, o)
cfmt, o = u16arr(d, o); ifmt, o = u16arr(d, o)
man, o = pstr(d, o); model, o = pstr(d, o); ver, o = pstr(d, o); ser, o = pstr(d, o)
print(f'std {std} vendorext 0x{vid:x} v{vver} "{ext}" mode {fmode}')
print(f'{man} | {model} | {ver}')
print('operations:', ' '.join(f'{x:04x}' for x in ops))
print('events:    ', ' '.join(f'{x:04x}' for x in evs))
print('props:     ', ' '.join(f'{x:04x}' for x in props))
print('OpenSession ->', hex(op(0x1002, 1)[0]))
print('CloseSession ->', hex(op(0x1003)[0]))
