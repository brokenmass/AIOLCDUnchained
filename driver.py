from io import BytesIO
import time
import hid
import math
from winusbcdc import WinUsbPy
from typing import Tuple
from collections import namedtuple
from enum import Enum, IntEnum
from PIL import Image, ImageDraw
from utils import debounce, timing, debugUsb

_NZXT_VID = 0x1E71
_DEFAULT_TIMEOUT_MS = 1000
_HID_WRITE_LENGTH = 64
_HID_READ_LENGTH = 64
_MAX_READ_UNTIL_RETRIES = 50
_COMMON_WRITE_HEADER = [
    0x12,
    0xFA,
    0x01,
    0xE8,
    0xAB,
    0xCD,
    0xEF,
    0x98,
    0x76,
    0x54,
    0x32,
    0x10,
]

Resolution = namedtuple("Resolution", ["width", "height"])


class RENDERING_MODE(str, Enum):
    RGBA = "RGBA"
    GIF = "GIF"
    FAST_GIF = "FAST_GIF"


class DISPLAY_MODE(IntEnum):
    LIQUID = 2
    BUCKET = 4
    FAST_BUCKET = 5


SUPPORTED_DEVICES = [
    {
        "pid": 0x3008,
        "name": "Kraken Z3",
        "resolution": Resolution(320, 320),
        "renderingMode": RENDERING_MODE.RGBA,
        "image": "http://127.0.0.1:30003/images/z3.png",
        "totalBuckets": 16,
        "maxBucketSize": 20 * 1024 * 1024,  # 20MB
        "supportsLiquidMode": True,
    },
    {
        "pid": 0x300E,
        "name": "Kraken 2023",
        "resolution": Resolution(240, 240),
        "renderingMode": RENDERING_MODE.RGBA,
        "image": "http://127.0.0.1:30003/images/2023.png",
        "totalBuckets": 1,
        "maxBucketSize": 46 * 1024,  # 46KB
        "supportsLiquidMode": False,
    },
    {
        "pid": 0x300C,
        "name": "Kraken Elite",
        "resolution": Resolution(640, 640),
        "renderingMode": RENDERING_MODE.FAST_GIF,
        "image": "http://127.0.0.1:30003/images/2023elite.png",
        "totalBuckets": 16,
        "maxBucketSize": 20 * 1024 * 1024,  # 20MB
        "supportsLiquidMode": True,
    },
]


class KrakenLCD:
    pid: int
    serial: str
    name: str
    resolution: Resolution
    totalBuckets: int
    maxBucketSize: int
    maxRGBABucketSize: int
    supportsLiquidMode: bool
    renderingMode: RENDERING_MODE
    lastReadMessage: bytes
    streamReady = False
    nextFrameBucket = 0
    bucketsToUse = 2
    black: Image.Image
    mask: Image.Image

    def __init__(self):
        for dev in SUPPORTED_DEVICES:
            info = hid.enumerate(_NZXT_VID, dev["pid"])
            if len(info) > 0:
                self.hidInfo = info[0]
                self.name = dev["name"]

                self.pid = dev["pid"]
                self.resolution: Resolution = dev["resolution"]
                self.renderingMode = dev["renderingMode"]
                self.image = dev["image"]
                self.totalBuckets = dev["totalBuckets"]
                self.supportsLiquidMode = dev["supportsLiquidMode"]
                self.maxBucketSize = dev["maxBucketSize"]
                self.maxRGBABucketSize: int = min(
                    dev["maxBucketSize"],
                    (self.resolution.width * self.resolution.height * 4),
                )
                self.bucketsToUse = max(self.totalBuckets, 2)
                print()
                break
        else:
            raise Exception("No supported device found")

        try:
            self.serial = self.hidInfo["serial_number"]
            self.hidDev = hid.device()
            self.hidDev.open_path(self.hidInfo["path"])
            self.bulkDev = WinUsbPy()

            for device in self.bulkDev.list_usb_devices(
                deviceinterface=True, present=True, findparent=True
            ):
                if (
                    device.path.find("vid_{:x}&pid_{:x}".format(_NZXT_VID, self.pid))
                    != -1
                    and device.parent
                    and device.parent.find(self.hidInfo["serial_number"]) != -1
                ):
                    self.bulkDev.init_winusb_device_with_path(device.path)
        except Exception:
            raise Exception("Could not connect to kraken device. Is NZXT CAM closed ?")

        self.black = Image.new("RGBA", self.resolution, (0, 0, 0, 0))
        self.mask = Image.new("RGBA", self.resolution, (0, 0, 0, 0))
        maskCanvas = ImageDraw.Draw(self.mask)
        maskCanvas.ellipse([(0, 0), self.resolution], fill=(255, 255, 255, 255))

        self.write([0x36, 0x3])
        self.setBrightness(100)

    def getInfo(self):
        return {
            "serial": self.serial,
            "name": self.name,
            "resolution": {
                "width": self.resolution.width,
                "height": self.resolution.height,
            },
            "renderingMode": self.renderingMode,
            "image": self.image,
        }

    def read(self, length=_HID_READ_LENGTH, timeout=_DEFAULT_TIMEOUT_MS):
        self.hidDev.set_nonblocking(False)
        self.lastReadMessage = self.hidDev.read(max_length=length, timeout_ms=timeout)
        if timeout and not self.lastReadMessage:
            raise Exception("Read timeout")
        return self.lastReadMessage

    @timing
    def clear(self):
        if self.hidDev.set_nonblocking(True) == 0:
            timeout_ms = 0
        else:
            timeout_ms = 1
        discarded = 0
        while self.hidDev.read(max_length=64, timeout_ms=timeout_ms):
            discarded += 1

    @timing
    def readUntil(self, parsers):
        for _ in range(_MAX_READ_UNTIL_RETRIES):
            msg = self.read()
            prefix = bytes(msg[0:2])
            func = parsers.pop(prefix, None)
            if func:
                return func(msg)
            if not parsers:
                return
        assert (
            False
        ), f"missing messages (attempts={_MAX_READ_UNTIL_RETRIES}, missing={len(parsers)})"

    @timing
    def write(self, data) -> int:
        self.hidDev.set_nonblocking(False)
        padding = [0x0] * (_HID_WRITE_LENGTH - len(data))
        res = self.hidDev.write(data + padding)
        if res < 0:
            raise OSError("Could not write to device")
        if res != _HID_WRITE_LENGTH:
            debugUsb("wrote %d total bytes, expected %d", res, _HID_WRITE_LENGTH)
        return res

    @timing
    def bulkWrite(self, data: bytes) -> None:
        self.bulkDev.write(0x2, data)

    def parseStandardResult(self, packet) -> bool:
        return packet[14] == 1

    def formatStandardResult(
        self, op: str, bucket: int, status: bool, tentative: int = -1
    ) -> str:
        resultMessage = (
            "Success" if status else "Fail[{}]".format(self.lastReadMessage[14])
        )
        tentativeText = "[{}]".format(tentative)
        return "{:20} bucket {:2}: {}".format(
            op + (tentativeText if (tentative > 0) else ""),
            bucket,
            resultMessage,
        )

    def parseStats(self, packet):
        return {"liquid": packet[15] + packet[16] / 10, "pump": packet[19]}

    @timing
    def getStats(self):
        self.write([0x74, 0x1])
        return self.readUntil({b"\x75\x01": self.parseStats})

    @debounce(0.5)
    def setBrightness(self, brightness: int) -> None:
        self.write(
            [
                0x30,
                0x02,
                0x01,
                max(0, min(100, brightness)),
                0x0,
                0x0,
                0x1,
                0x3,  # default orientation,
            ]
        )

    @timing
    def setLcdMode(self, mode: DISPLAY_MODE, bucket=0) -> bool:
        self.write([0x38, 0x1, mode, bucket])
        return self.readUntil({b"\x39\x01": self.parseStandardResult})

    @timing
    def deleteBucket(self, bucket: int, retries=1) -> bool:
        status = False
        for i in range(retries):
            self.write([0x32, 0x2, bucket])
            status = self.readUntil({b"\x33\x02": self.parseStandardResult})
            debugUsb(self.formatStandardResult("Delete", bucket, status, i))
            if status:
                return True
        else:
            return False

    @timing
    def deleteAllBuckets(self):
        for bucket in range(self.totalBuckets):
            for i in range(10):
                status = self.deleteBucket(bucket, i)

                if status:
                    break
                time.sleep(0.1)
            else:
                raise Exception("Could not delete bucket {}".format(bucket))

    @timing
    def createBucket(
        self,
        bucket: int,
        address: Tuple[int, int] = [0, 0],
        size: int = None,
    ):
        sizeBytes = list(
            math.ceil((size or self.maxRGBABucketSize) / 1024 + 1).to_bytes(2, "little")
        )
        self.write(
            [
                0x32,
                0x01,
                bucket,
                bucket + 1,
                address[0],
                address[1],
                sizeBytes[0],
                sizeBytes[1],
                0x01,
            ]
        )
        status = self.readUntil({b"\x33\x01": self.parseStandardResult})
        debugUsb(self.formatStandardResult("Create", bucket, status))
        return status

    @timing
    def writeRGBA(self, RGBAData: bytes, bucket: int) -> bool:
        self.write([0x36, 0x01, bucket])
        status = self.readUntil({b"\x37\x01": self.parseStandardResult})
        debugUsb(self.formatStandardResult("Start writeRGBA", bucket, status))
        if not status:
            return False

        header = (
            _COMMON_WRITE_HEADER
            + [
                0x02,
                0x00,
                0x00,
                0x00,
            ]
            + list(len(RGBAData).to_bytes(4, "little"))
        )

        self.bulkWrite(bytes(header))
        self.bulkWrite(RGBAData)

        self.write([0x36, 0x02, bucket])
        status = self.readUntil({b"\x37\x02": self.parseStandardResult})
        debugUsb(self.formatStandardResult("End writeRGBA", bucket, status))
        return status

    @timing
    def writeGIF(self, gifData: bytes, bucket: int, fast=True) -> bool:
        # 4th byte set as 1 writes to some sort of fast memory in kraken elite (bucket number is not relevant)
        self.write([0x36, 0x01, bucket, 0x1 if fast else 0x0])
        status = self.readUntil({b"\x37\x01": self.parseStandardResult})
        debugUsb(self.formatStandardResult("Start writeGIF", bucket, status))
        if not status:
            return False

        header = (
            _COMMON_WRITE_HEADER
            + [
                0x01,
                0x00,
                0x00,
                0x00,
            ]
            + list(len(gifData).to_bytes(4, "little"))
        )

        self.bulkWrite(bytes(header))

        self.bulkWrite(gifData)

        self.write([0x36, 0x02, bucket])
        status = self.readUntil({b"\x37\x02": self.parseStandardResult})
        debugUsb(self.formatStandardResult("End writeGIF", bucket, status))
        return status

    @timing
    def writeFrame(self, frame: bytes):
        if not self.streamReady:
            return False
        self.clear()
        result = False
        if self.renderingMode == RENDERING_MODE.RGBA:
            result = self.writeRGBA(frame, self.nextFrameBucket) and self.setLcdMode(
                DISPLAY_MODE.BUCKET, self.nextFrameBucket
            )
        if self.renderingMode == RENDERING_MODE.GIF:
            startAddress = list(
                math.ceil(
                    self.nextFrameBucket * ((self.maxRGBABucketSize) / 1024 + 1)
                ).to_bytes(2, "little")
            )

            result = (
                (
                    self.deleteBucket(self.nextFrameBucket)
                    or self.deleteBucket(self.nextFrameBucket)
                )
                and self.createBucket(self.nextFrameBucket, startAddress)
                and self.writeGIF(frame, self.nextFrameBucket, fast=False)
                and self.setLcdMode(DISPLAY_MODE.BUCKET, self.nextFrameBucket)
            )
        if self.renderingMode == RENDERING_MODE.FAST_GIF:
            result = self.writeGIF(frame, 0, fast=True) and self.setLcdMode(
                DISPLAY_MODE.FAST_BUCKET, 0
            )
        self.nextFrameBucket = (self.nextFrameBucket + 1) % self.bucketsToUse
        return result

    @timing
    def imageToFrame(self, img: Image.Image, adaptive=False) -> bytes:
        # cut the image to circular frame. This reduce gif size by ~20%
        img = Image.composite(img, self.black, self.mask)

        if self.renderingMode == RENDERING_MODE.RGBA:
            raw = list(img.convert("RGB").getdata())
            output = []
            for i in range(img.size[0] * img.size[1]):
                output.append(raw[i][0])
                output.append(raw[i][1])
                output.append(raw[i][2])
                output.append(0)
            return bytes(output)
        else:
            # Ideas for improving performance/quality, unfortunately pillow has multiple bugs like
            # https://github.com/python-pillow/Pillow/issues/5836
            #
            # A) variable palette
            # img.convert("RGB").convert(
            #     "P", palette=Image.Palette.ADAPTIVE, colors=colors
            # ).save(byteio, "GIF", interlace=False)

            # B) dithering
            # img = img.convert("RGB")
            # pal = img.quantize(colors)
            # img = img.quantize(
            #     colors, palette=pal, dither=Image.FLOYDSTEINBERG
            # )
            byteio = BytesIO()

            @timing
            def convert():
                nonlocal img
                if adaptive:
                    img = img.convert("RGB").convert(
                        "P", palette=Image.Palette.ADAPTIVE, colors=64
                    )
                else:
                    img = img.convert("RGB").convert("P")

            @timing
            def save():
                img.save(byteio, "GIF", interlace=False, optimize=True)

            convert()
            save()
            return byteio.getvalue()

    @timing
    def setupStream(self):
        if self.supportsLiquidMode:
            self.setLcdMode(DISPLAY_MODE.LIQUID, 0x0)
            time.sleep(0.1)

        if self.renderingMode == RENDERING_MODE.RGBA:
            self.deleteAllBuckets()
            for i in range(self.bucketsToUse):
                startAddress = list(
                    math.ceil(i * ((self.maxRGBABucketSize) / 1024 + 1)).to_bytes(
                        2, "little"
                    )
                )
                self.createBucket(i, startAddress)

        self.setLcdMode(DISPLAY_MODE.BUCKET, 0x0)
        self.streamReady = True


# for bucket in range(16):
#     driver.self.write([0x30, 0x04, bucket])  # query bucket
#     msg = self.read()
#     d.append([bucket, int.from_bytes([msg[17], msg[18]], "little"), int.from_bytes([msg[19], msg[20]], "little") ])
#     debugUsb("Bucket {:2} | start {:6} | size: {:6} ".format(bucket, int.from_bytes([msg[17], msg[18]], "little"), int.from_bytes([msg[19], msg[20]], "little"), LazyHexRepr(msg)))
