import hid
import math
from winusbcdc import WinUsbPy
from typing import Tuple, List

_DEFAULT_TIMEOUT_MS = 1000
_HID_WRITE_LENGTH = 64
_HID_READ_LENGTH = 64
_WIDTH = 640
_HEIGHT = 640
_MAX_RGBA_BUCKET_SIZE = _WIDTH * _HEIGHT * 4


bulkDev = WinUsbPy()
hidInfo = hid.enumerate(0x1E71, 0x300c)[0]
hidDev = hid.device()
hidDev.open_path(hidInfo['path'])

for device in bulkDev.list_usb_devices(deviceinterface=True, present=True, findparent=True):
    if (
        device.path.find("vid_1e71&pid_300c") != -1
        and device.parent
        and device.parent.find(hidInfo['serial_number']) != -1
    ):
        bulkDev.init_winusb_device_with_path(device.path)


def read(length=_HID_READ_LENGTH, *, timeout=_DEFAULT_TIMEOUT_MS):
    hidDev.set_nonblocking(False)
    data = hidDev.read(max_length=length, timeout_ms=timeout)
    if timeout and not data:
        raise "timeout"
    return data


def clear():
    if hidDev.set_nonblocking(True) == 0:
        timeout_ms = 0  # use hid_read; wont block because call succeeded
    else:
        timeout_ms = 1  # smallest timeout forwarded to hid_read_timeout
    discarded = 0
    while hidDev.read(max_length=64, timeout_ms=timeout_ms):
        discarded += 1


def readUntil(parsers):
    for _ in range(200):
        msg = read()
        prefix = bytes(msg[0:2])
        func = parsers.pop(prefix, None)
        if func:
            return func(msg)
        if not parsers:
            return
    assert False, f"missing messages (attempts={50}, missing={len(parsers)})"


def write(data):
    hidDev.set_nonblocking(False)
    padding = [0x0] * (_HID_WRITE_LENGTH - len(data))
    res = hidDev.write(data + padding)
    if res < 0:
        raise OSError('Could not write to device')
    if res != len(data + padding):
        print('wrote %d total bytes, expected %d', res, len(data + padding))
    return res


def bulkWrite(data: bytes):

    bulkDev.write(0x2, data)


def parseResult(m):
    return m[14] == 1


def setLcdMode(mode: int, bucket=0) -> bool:
    write([0x38, 0x1, mode, bucket])
    return readUntil({b"\x39\x01": parseResult})


def deleteBucket(bucket: int) -> bool:
    write([0x32, 0x2, bucket])
    return readUntil({b"\x33\x02": parseResult})


def createBucket(bucket: int, address: Tuple[int, int] = [0, 0], size: int = _MAX_RGBA_BUCKET_SIZE):
    sizeBytes = list(math.ceil(size / 1024).to_bytes(2, "little"))
    write([0x32, 0x01, bucket, bucket + 1, address[0],
          address[1], sizeBytes[0], sizeBytes[1], 0x01])
    return readUntil({b"\x33\x01": parseResult})


def writeRGBA(bucket: int, RGBAData: List[int]):
    write([0x36, 0x01, bucket])
    status = readUntil({b"\x37\x01": parseResult})
    if not status:
        return False

    header = [0x12, 0xFA, 0x01, 0xE8, 0xAB, 0xCD, 0xEF, 0x98, 0x76, 0x54, 0x32, 0x10,
              0x02, 0x00, 0x00, 0x00] + list(len(RGBAData).to_bytes(4, "little"))

    bulkWrite(bytes(header))
    bulkWrite(bytes(RGBAData))

    write([0x36, 0x02, bucket])
    return readUntil({b"\x37\x02": parseResult})


def writeGIF(bucket: int, gifData: bytes, fast=True):
    # 4th byte set as 1 might indicate some sort of fast writing mode (or blocking)
    write([0x36, 0x01, bucket, 0x1 if fast else 0x0])
    status = readUntil({b"\x37\x01": parseResult})
    if not status:
        return False

    header = [0x12, 0xFA, 0x01, 0xE8, 0xAB, 0xCD, 0xEF, 0x98, 0x76, 0x54, 0x32, 0x10,
              0x01, 0x00, 0x00, 0x00] + list(len(gifData).to_bytes(4, "little"))

    bulkWrite(bytes(header))
    bulkWrite(gifData)

    write([0x36, 0x02, bucket])
    return readUntil({b"\x37\x02": parseResult})


# for bucket in range(16):
#     driver.write([0x30, 0x04, bucket])  # query bucket
#     msg = read()
#     d.append([bucket, int.from_bytes([msg[17], msg[18]], "little"), int.from_bytes([msg[19], msg[20]], "little") ])
#     print("Bucket {:2} | start {:6} | size: {:6} ".format(bucket, int.from_bytes([msg[17], msg[18]], "little"), int.from_bytes([msg[19], msg[20]], "little"), LazyHexRepr(msg)))
