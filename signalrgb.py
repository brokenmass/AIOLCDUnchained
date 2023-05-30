import traceback
import time
import driver
import time
import math
import socket
from PIL import Image, ImageFont, ImageDraw
from io import BytesIO
from mss import mss
import queue
from threading import Thread
from utils import FPS
import json
import psutil
import os

from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver
import base64

FONT_FILE = "./fonts/Rubik-Bold.ttf"

MIN_SPEED = 2
BASE_SPEED = 18
MIN_COLORS = 64
stats = {
    "cpu": 0,
    "pump": 0,
    "liquid": 0,
}

# initial palette size
colors = MIN_COLORS * 2


class RawProducer(Thread):
    def __init__(self, rawBuffer: queue.Queue):
        Thread.__init__(self)
        self.daemon = True
        self.rawBuffer = rawBuffer

    def run(self):
        print("Server worker started")
        frameCount = 0
        rawBuffer = self.rawBuffer
        lastFrame = time.time()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def _set_response(self):
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.send_header("Connection", "keep-alive")
                self.send_header("keep-alive", "timeout=5, max=30")
                self.send_header("Content-Length", 0)
                self.end_headers()

            def do_HEAD(self):
                self._set_headers()

            def do_GET(self):
                self._set_response()

            def do_POST(self):
                nonlocal lastFrame
                content_length = int(self.headers["Content-Length"])
                post_data = self.rfile.read(content_length)
                rawTime = time.time() - lastFrame
                rawBuffer.put((post_data, rawTime))
                lastFrame = time.time()
                self._set_response()

        server_address = ("", 30003)
        httpd = HTTPServer(server_address, Handler)
        httpd.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        httpd.serve_forever()


# UDP SERVER TEST
# class RawProducer(Thread):
#     def __init__(self, rawBuffer: queue.Queue):
#         Thread.__init__(self)
#         self.daemon = True
#         self.rawBuffer = rawBuffer
#     def run(self):
#         print('Server worker started')
#         frameCount = 0
#         lastFrame = time.time()
#         buffer = bytes()
#         expectedSize = 0
#         class ThreadedUDPRequestHandler(socketserver.BaseRequestHandler):
#             def handle(self):
#                 nonlocal lastFrame
#                 nonlocal buffer
#                 nonlocal expectedSize
#                 data: bytes = self.request[0].strip()
#                 rawTime = time.time() - lastFrame
#                 rawBuffer.put((base64.b64decode(data.decode('utf-8')), rawTime))
#                 lastFrame = time.time()
#                 # data: bytes = self.request[0].strip()
#                 # if len(data) <= 8 and data[:4] == b'\xff\xaa\xbb\xff':
#                 #     expectedSize = int.from_bytes(data[4:], byteorder='big')
#                 #     buffer = bytes()
#                 # else:
#                 #     buffer += data
#                 # if len(buffer) == expectedSize:
#                 #     rawTime = time.time() - lastFrame
#                 #     rawBuffer.put((buffer, rawTime))
#                 #     buffer = bytes()
#                 #     lastFrame = time.time()
#         class ThreadedUDPServer(socketserver.ThreadingMixIn, socketserver.UDPServer):
#             pass
#         server = ThreadedUDPServer(('127.0.0.1', 9999), ThreadedUDPRequestHandler)
#         server.serve_forever()


class GifProducer(Thread):
    def __init__(self, rawBuffer: queue.Queue, gifBuffer: queue.Queue):
        Thread.__init__(self)
        self.daemon = True
        self.rawBuffer = rawBuffer
        self.gifBuffer = gifBuffer
        self.lastAngle = 0
        self.circleImg = Image.new(
            "RGBA", (driver._WIDTH, driver._HEIGHT), (0, 0, 0, 0)
        )
        self.fonts = {
            "titleFontSize": 10,
            "sensorFontSize": 10,
            "fontTitle": ImageFont.truetype(FONT_FILE, 10),
            "fontSensor": ImageFont.truetype(FONT_FILE, 10),
            "fontDegree": ImageFont.truetype(FONT_FILE, 10 // 3),
        }

    def updateFonts(self, data):
        if data["titleFontSize"] != self.fonts["titleFontSize"]:
            data["titleFontSize"] = data["titleFontSize"]
            self.fonts["fontTitle"] = ImageFont.truetype(
                FONT_FILE, data["titleFontSize"]
            )
        if data["sensorFontSize"] != self.fonts["sensorFontSize"]:
            data["sensorFontSize"] = data["sensorFontSize"]
            self.fonts["fontSensor"] = ImageFont.truetype(
                FONT_FILE, data["sensorFontSize"]
            )
            self.fonts["fontDegree"] = ImageFont.truetype(
                FONT_FILE, data["sensorFontSize"] // 3
            )

    def run(self):
        print("Gif converter worker started")
        while True:
            if self.gifBuffer.full():
                time.sleep(0.005)
                continue

            (post_data, rawTime) = self.rawBuffer.get()
            startTime = time.time()
            try:
                data = json.loads(post_data.decode("utf-8"))
                raw = base64.b64decode(data["raw"])

                img = (
                    Image.open(BytesIO(raw))
                    .convert("RGBA")
                    .resize((driver._WIDTH, driver._HEIGHT), Image.Resampling.LANCZOS)
                )

                if data["composition"] != "OFF":
                    alpha = 255
                    if data["composition"] == "OVERLAY":
                        alpha = round((100 - data["overlayTransparency"]) * 255 / 100)
                    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
                    overlayCanvas = ImageDraw.Draw(overlay)

                    if data["spinner"] == "CPU" or data["spinner"] == "PUMP":
                        bands = list(self.circleImg.split())
                        bands[3] = bands[3].point(
                            lambda x: round(x / 1.1) if x > 10 else 0
                        )
                        self.circleImg = Image.merge(self.circleImg.mode, bands)
                        circleCanvas = ImageDraw.Draw(self.circleImg)

                        angle = (
                            MIN_SPEED
                            + BASE_SPEED * stats[data["spinner"].lower()] / 100
                        )

                        newAngle = self.lastAngle + angle
                        circleCanvas.arc(
                            [(0, 0), (driver._WIDTH, driver._HEIGHT)],
                            fill=(255, 255, 255, round(alpha / 1.05)),
                            width=driver._WIDTH // 20,
                            start=self.lastAngle,
                            end=self.lastAngle + angle / 2,
                        )
                        circleCanvas.arc(
                            [(0, 0), (driver._WIDTH, driver._HEIGHT)],
                            fill=(255, 255, 255, alpha),
                            width=driver._WIDTH // 20,
                            start=self.lastAngle + angle / 2,
                            end=newAngle,
                        )
                        self.lastAngle = newAngle
                        overlay.paste(self.circleImg)

                    if data["spinner"] == "STATIC":
                        overlayCanvas.ellipse(
                            [(0, 0), (driver._WIDTH, driver._HEIGHT)],
                            outline=(255, 255, 255, alpha),
                            width=driver._WIDTH // 20,
                        )
                    if data["textOverlay"]:
                        self.updateFonts(data)
                        overlayCanvas.text(
                            (driver._WIDTH // 2, driver._HEIGHT // 5),
                            text=data["titleText"],
                            anchor="mm",
                            align="center",
                            font=self.fonts["fontTitle"],
                            fill=(255, 255, 255, alpha),
                        )
                        overlayCanvas.text(
                            (driver._WIDTH // 2, driver._HEIGHT // 2),
                            text="{:.0f}".format(stats["liquid"]),
                            anchor="mm",
                            align="center",
                            font=self.fonts["fontSensor"],
                            fill=(255, 255, 255, alpha),
                        )
                        textBbox = overlayCanvas.textbbox(
                            (driver._WIDTH // 2, driver._HEIGHT // 2),
                            text="{:.0f}".format(stats["liquid"]),
                            anchor="mm",
                            align="center",
                            font=self.fonts["fontSensor"],
                        )
                        overlayCanvas.text(
                            ((textBbox[2], textBbox[1])),
                            text="°",
                            anchor="lt",
                            align="center",
                            font=self.fonts["fontDegree"],
                            fill=(255, 255, 255, alpha),
                        )
                        overlayCanvas.text(
                            (driver._WIDTH // 2, 4 * driver._HEIGHT // 5),
                            text="Liquid",
                            anchor="mm",
                            align="center",
                            font=self.fonts["fontTitle"],
                            fill=(255, 255, 255, alpha),
                        )

                    if data["composition"] == "MIX":
                        img = Image.composite(
                            img,
                            Image.new("RGBA", img.size, (0, 0, 0, 0)),
                            overlay.rotate(data["rotation"]),
                        )

                    if data["composition"] == "OVERLAY":
                        img = Image.alpha_composite(
                            img, overlay.rotate(data["rotation"])
                        )

                byteio = BytesIO()
                #  variable palette
                # img.convert("RGB").convert(
                #     "P", palette=Image.Palette.ADAPTIVE, colors=colors
                # ).save(byteio, "GIF", interlace=False)

                #  dithering
                # img = img.convert("RGB")
                # pal = img.quantize(colors)
                # dither_lesscol = img.quantize(
                #     colors, palette=pal, dither=Image.FLOYDSTEINBERG
                # )
                # dither_lesscol.save(byteio, "GIF", interlace=False, optimize=True)

                img.convert("RGB").convert("P").save(byteio, "GIF", interlace=False)
                self.gifBuffer.put(
                    (byteio.getvalue(), rawTime, time.time() - startTime)
                )
            except Exception:
                print(traceback.format_exc())
                pass


class StatsProducer(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True

    def run(self):
        while True:
            stats["cpu"] = psutil.cpu_percent(1)


driver.setLcdMode(0x2, 0x1)
time.sleep(0.2)

for bucket in range(16):
    status = False
    while not status:
        status = driver.deleteBucket(bucket)
        print("Bucket {} deleted: {}".format(bucket, status))


status = driver.createBucket(0)
print("Bucket {} created: {}".format(0, status))

# write full black RGBA
driver.writeRGBA(0, [0x0, 0x0, 0x0, 0xFF] * (driver._WIDTH * driver._HEIGHT))
driver.setLcdMode(0x4, 0x0)

time.sleep(0.2)

rawBuffer = queue.Queue(maxsize=2)
gifBuffer = queue.Queue(maxsize=2)
rawProducer = RawProducer(rawBuffer)
gifProducer = GifProducer(rawBuffer, gifBuffer)
statsProducer = StatsProducer()
statsProducer.start()
rawProducer.start()
gifProducer.start()
frameCount = 0
fps = FPS()
lastDataTime = 0


while True:
    try:
        (frame, rawTime, gifTime) = gifBuffer.get()
        startTime = time.time()
        driver.clear()
        driver.writeGIF(0x0, frame)
        driver.setLcdMode(0x5, 0x0)
        writeTime = time.time() - startTime
        freeTime = (rawTime - writeTime) * 1000

        print(
            "FPS: {:.1f} - Frame {:5} (size: {:7}) - raw {:.2f}ms, gif {:.2f}ms, write {:.2f}ms  - Colors {:3} {:3.2f}ms free time".format(
                fps(),
                frameCount,
                len(frame),
                rawTime * 1000,
                gifTime * 1000,
                writeTime * 1000,
                colors,
                freeTime,
            )
        )
        # dynamically adjust gif color precisione (and size) base on how much 'free time' we have.

        if freeTime > 5 and colors < 256:
            colors = min(256, round(colors * 1.05))
        if freeTime < -2 and colors > 8:
            colors = max(MIN_COLORS, round(colors * 0.95))

        frameCount = frameCount + 1
        now = time.time()
        if now - lastDataTime > 1:
            lastDataTime = now
            driver.write([0x74, 0x1])
            packet = driver.read()
            stats["liquid"] = packet[15] + packet[16] / 10
            stats["pump"] = packet[19]

        else:
            pass
            # fps()
    except Exception as e:
        traceback.print_exc()
        time.sleep(0.001)
