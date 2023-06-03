import time
import driver
import time
import pystray
from PIL import Image, ImageFont, ImageDraw
from io import BytesIO
from mss import mss
import queue
from threading import Thread
from utils import debug
import json
import psutil
import sys
import os
from workers import FrameWriter
from http.server import BaseHTTPRequestHandler, HTTPServer
import base64
from socketserver import ThreadingMixIn
import shutil
from pathlib import Path

PORT = 30003
BASE_PATH = "."
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    BASE_PATH = sys._MEIPASS

FONT_FILE = os.path.join(BASE_PATH, "fonts/Rubik-Bold.ttf")
APP_ICON = os.path.join(BASE_PATH, "images/plugin.png")

MIN_SPEED = 2
BASE_SPEED = 18

stats = {
    "cpu": 0,
    "pump": 0,
    "liquid": 0,
}

# dyanmicPalette test
MIN_COLORS = 64
colors = MIN_COLORS * 2


lcd = driver.KrakenLCD()
lcd.setupStream()

pluginInstalled = False
try:
    shutil.copytree(
        os.path.join(BASE_PATH, "SignalRGBPlugin"),
        os.path.join(Path.home(), "Documents/WhirlwindFX/Plugins/KrakenLCDBridge/"),
        dirs_exist_ok=True,
    )
    print("Successfully installed SignalRGB plugin")
    pluginInstalled = True

except Exception:
    print("Could not automatically install SignalRGB plugin")


ThreadingMixIn.daemon_threads = True


class RawProducer(Thread):
    def __init__(self, rawBuffer: queue.Queue):
        Thread.__init__(self)
        self.daemon = True
        self.rawBuffer = rawBuffer

    def run(self):
        debug("Server worker started")
        rawBuffer = self.rawBuffer
        lastFrame = time.time()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def _set_headers(self, contentType="application/json"):
                self.send_response(200)
                self.send_header("Content-type", contentType)
                self.end_headers()

            def do_HEAD(self):
                self._set_headers()

            def do_GET(self):
                if (
                    self.path == "/images/2023elite.png"
                    or self.path == "/images/2023.png"
                    or self.path == "/images/z3.png"
                    or self.path == "/images/plugin.png"
                ):
                    file = open(BASE_PATH + self.path, "rb")
                    data = file.read()
                    file.close()
                    self._set_headers("image/png")
                    self.wfile.write(data)
                else:
                    self._set_headers()
                    self.wfile.write(bytes(json.dumps(lcd.getInfo()), "utf-8"))

            def do_POST(self):
                nonlocal lastFrame
                if self.path == "/brightness":
                    post_data = self.rfile.read(
                        int(self.headers["Content-Length"] or "0")
                    )
                    data = json.loads(post_data.decode("utf-8"))
                    lcd.setBrightness(data["brightness"])
                if self.path == "/frame":
                    post_data = self.rfile.read(
                        int(self.headers["Content-Length"] or "0")
                    )
                    rawTime = time.time() - lastFrame
                    rawBuffer.put((post_data, rawTime))
                    lastFrame = time.time()
                self._set_headers()

        class ThreadingSimpleServer(ThreadingMixIn, HTTPServer):
            pass

        server_address = ("", PORT)
        server = ThreadingSimpleServer(server_address, Handler)
        # httpd.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        server.serve_forever()


class OverlayProducer(Thread):
    def __init__(self, rawBuffer: queue.Queue, frameBuffer: queue.Queue):
        Thread.__init__(self)
        self.daemon = True
        self.rawBuffer = rawBuffer
        self.frameBuffer = frameBuffer
        self.lastAngle = 0
        self.circleImg = Image.new("RGBA", lcd.resolution, (0, 0, 0, 0))
        self.fonts = {
            "titleFontSize": 10,
            "sensorFontSize": 100,
            "sensorLabelFontSize": 10,
            "fontTitle": ImageFont.truetype(FONT_FILE, 10),
            "fontSensor": ImageFont.truetype(FONT_FILE, 100),
            "fontSensorLabel": ImageFont.truetype(FONT_FILE, 10),
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
        if data["sensorLabelFontSize"] != self.fonts["sensorLabelFontSize"]:
            data["sensorLabelFontSize"] = data["sensorLabelFontSize"]
            self.fonts["fontSensorLabel"] = ImageFont.truetype(
                FONT_FILE, data["sensorLabelFontSize"]
            )

    def run(self):
        debug("Overlay converter worker started")
        while True:
            if self.frameBuffer.full():
                time.sleep(0.001)
                continue

            (post_data, rawTime) = self.rawBuffer.get()
            startTime = time.time()

            data = json.loads(post_data.decode("utf-8"))
            raw = base64.b64decode(data["raw"])

            img = (
                Image.open(BytesIO(raw))
                .convert("RGBA")
                .resize(
                    lcd.resolution,
                    Image.Resampling.LANCZOS,
                )
            )

            if data["composition"] != "OFF":
                alpha = 255
                if data["composition"] == "OVERLAY":
                    alpha = round((100 - data["overlayTransparency"]) * 255 / 100)
                overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
                overlayCanvas = ImageDraw.Draw(overlay)

                if data["spinner"] == "CPU" or data["spinner"] == "PUMP":
                    bands = list(self.circleImg.split())
                    bands[3] = bands[3].point(lambda x: round(x / 1.1) if x > 10 else 0)
                    self.circleImg = Image.merge(self.circleImg.mode, bands)
                    circleCanvas = ImageDraw.Draw(self.circleImg)

                    angle = (
                        MIN_SPEED + BASE_SPEED * stats[data["spinner"].lower()] / 100
                    )

                    newAngle = self.lastAngle + angle
                    circleCanvas.arc(
                        [(0, 0), lcd.resolution],
                        fill=(255, 255, 255, round(alpha / 1.05)),
                        width=lcd.resolution.width // 20,
                        start=self.lastAngle,
                        end=self.lastAngle + angle / 2,
                    )
                    circleCanvas.arc(
                        [(0, 0), lcd.resolution],
                        fill=(255, 255, 255, alpha),
                        width=lcd.resolution.width // 20,
                        start=self.lastAngle + angle / 2,
                        end=newAngle,
                    )
                    self.lastAngle = newAngle
                    overlay.paste(self.circleImg)

                if data["spinner"] == "STATIC":
                    overlayCanvas.ellipse(
                        [(0, 0), lcd.resolution],
                        outline=(255, 255, 255, alpha),
                        width=lcd.resolution.width // 20,
                    )
                if data["textOverlay"]:
                    self.updateFonts(data)
                    overlayCanvas.text(
                        (lcd.resolution.width // 2, lcd.resolution.height // 5),
                        text=data["titleText"],
                        anchor="mm",
                        align="center",
                        font=self.fonts["fontTitle"],
                        fill=(255, 255, 255, alpha),
                    )
                    overlayCanvas.text(
                        (lcd.resolution.width // 2, lcd.resolution.height // 2),
                        text="{:.0f}".format(stats["liquid"]),
                        anchor="mm",
                        align="center",
                        font=self.fonts["fontSensor"],
                        fill=(255, 255, 255, alpha),
                    )
                    textBbox = overlayCanvas.textbbox(
                        (lcd.resolution.width // 2, lcd.resolution.height // 2),
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
                        (lcd.resolution.width // 2, 4 * lcd.resolution.height // 5),
                        text="Liquid",
                        anchor="mm",
                        align="center",
                        font=self.fonts["fontSensorLabel"],
                        fill=(255, 255, 255, alpha),
                    )

                if data["composition"] == "MIX":
                    img = Image.composite(
                        img,
                        Image.new("RGBA", img.size, (0, 0, 0, 0)),
                        overlay.rotate(data["rotation"]),
                    )

                if data["composition"] == "OVERLAY":
                    img = Image.alpha_composite(img, overlay.rotate(data["rotation"]))

            self.frameBuffer.put(
                (
                    lcd.imageToFrame(img, adaptive=data["colorPalette"] == "ADAPTIVE"),
                    rawTime,
                    time.time() - startTime,
                )
            )


class StatsProducer(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True

    def run(self):
        debug("CPU stats producer started")
        while True:
            stats["cpu"] = psutil.cpu_percent(1)


class Systray(Thread):
    def __init__(self):
        Thread.__init__(self)
        # monkey patching pystray to open menu on left click
        from pystray._util import win32

        win32.WM_LBUTTONUP = 0x0205
        win32.WM_RBUTTONUP = 0x0202

        self.menu = pystray.Menu(
            pystray.MenuItem("Device: " + lcd.name, self.noop, enabled=False),
            pystray.MenuItem(
                "Bridge: http://127.0.0.1:{}".format(PORT), self.noop, enabled=False
            ),
            pystray.MenuItem(
                "SignalRGBPlugin: "
                + ("installed" if pluginInstalled else "not installed"),
                self.noop,
                enabled=False,
            ),
            pystray.MenuItem(
                self.getFPS,
                self.noop,
                enabled=False,
            ),
            pystray.MenuItem("Exit", self.stop),
        )
        self.icon = pystray.Icon(
            name="KrakenLCDBridge",
            title="KrakenLCDBridge",
            icon=Image.open(APP_ICON).resize((64, 64)),
            menu=self.menu,
        )

    def run(self):
        debug("Systray icon started")
        self.icon.run()

    def getFPS(self, _):
        return "FPS: {:.2f}".format(frameWriterWithStats.fps.value)

    def noop(self):
        pass

    def stop(self):
        self.icon.stop()


class FrameWriterWithStats(FrameWriter):
    def __init__(self, frameBuffer: queue.Queue, lcd: driver.KrakenLCD):
        super().__init__(frameBuffer, lcd)
        self.updateAIOStats()

    def updateAIOStats(self):
        if time.time() - self.lastDataTime > 1:
            self.lastDataTime = time.time()
            stats.update(self.lcd.getStats())

    def onFrame(self):
        super().onFrame()
        self.updateAIOStats()
        # dynamically adjust gif color precisione (and size) base on how much 'free time' we have.

        # if freeTime > 5 and colors < 256:
        #     colors = min(256, round(colors * 1.05))
        # if freeTime < -2 and colors > 8:
        #     colors = max(MIN_COLORS, round(colors * 0.95))


dataBuffer = queue.Queue(maxsize=2)
frameBuffer = queue.Queue(maxsize=2)

rawProducer = RawProducer(dataBuffer)
overlayProducer = OverlayProducer(dataBuffer, frameBuffer)
frameWriterWithStats = FrameWriterWithStats(frameBuffer, lcd)
statsProducer = StatsProducer()
systray = Systray()


rawProducer.start()
overlayProducer.start()
frameWriterWithStats.start()
statsProducer.start()
systray.start()

print("SignalRGB Kraken bridge started")


try:
    while True:
        time.sleep(1)
        systray.icon.update_menu()
        if not (
            statsProducer.is_alive()
            and rawProducer.is_alive()
            and overlayProducer.is_alive()
            and frameWriterWithStats.is_alive()
            and systray.is_alive()
        ):
            raise KeyboardInterrupt("Some thread is dead")
except KeyboardInterrupt:
    frameWriterWithStats.shouldStop = True
    frameWriterWithStats.join()
    systray.stop()
