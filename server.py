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
from threading import Thread, Event, Lock
from utils import FPS, LazyHexRepr
import json

from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver
import base64

FONT_FILE = './GothamBold.ttf'


class RawProducer(Thread):
    def __init__(self, rawBuffer: queue.Queue):
        Thread.__init__(self)
        self.daemon = True
        self.rawBuffer = rawBuffer

    def run(self):
        print('Server worker started')
        frameCount = 0
        rawBuffer = self.rawBuffer
        lastFrame = time.time()

        class Handler(BaseHTTPRequestHandler):

            def log_message(self, format, *args):
                return

            def _set_response(self):
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.send_header('Connection', 'keep-alive')
                self.send_header('keep-alive', 'timeout=5, max=30')
                self.send_header('Content-Length', 0)
                self.end_headers()

            def do_HEAD(self):
                self._set_headers()

            def do_GET(self):
                self._set_response()

            def do_POST(self):
                nonlocal lastFrame
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                rawTime = time.time() - lastFrame
                rawBuffer.put(
                    (post_data, rawTime))
                lastFrame = time.time()
                self._set_response()
        server_address = ('', 30003)
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


# initial palette size
palette = 32


class GifProducer(Thread):
    def __init__(self, rawBuffer: queue.Queue, gifBuffer: queue.Queue, paletteLock: Lock):
        Thread.__init__(self)
        self.daemon = True
        self.rawBuffer = rawBuffer
        self.gifBuffer = gifBuffer
        self.paletteLock = paletteLock

    def run(self):
        print('Gif converter worker started')
        while True:
            if self.gifBuffer.full():
                time.sleep(0.005)
                continue

            (post_data, rawTime) = self.rawBuffer.get()
            startTime = time.time()
            try:
                data = json.loads(post_data.decode('utf-8'))
                raw = base64.b64decode(data['raw'])
                fontSmall = ImageFont.truetype(
                    FONT_FILE, data['titleFontSize'])
                fontLarge = ImageFont.truetype(
                    FONT_FILE, data['sensorFontSize'])

                img = Image.open(BytesIO(raw)).resize(
                    (driver._WIDTH, driver._HEIGHT), Image.Resampling.LANCZOS).convert('RGBA')
                overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
                overlayCanvas = ImageDraw.Draw(overlay)
                transparency = round(
                    (100 - data['textTransparency']) * 255 / 100)
                overlayCanvas.text(
                    (320, 120),
                    text='SignalRGB',
                    anchor='mm',
                    align='center',
                    font=fontSmall,
                    fill=(255, 255, 255, transparency),
                    stroke_width=5,
                    stroke_fill=(0, 0, 0, round(transparency / 5))
                )
                overlayCanvas.text(
                    (320, 320),
                    text='{:.0f}'.format(28),
                    anchor='mm',
                    align='center',
                    font=fontLarge,
                    fill=(255, 255, 255, transparency),
                    stroke_width=5,
                    stroke_fill=(0, 0, 0, round(transparency / 5))
                )

                byteio = BytesIO()
                (Image.alpha_composite(img, overlay.rotate(data['rotation']))
                 .convert('RGB')
                 .convert('P', palette=Image.Palette.ADAPTIVE, colors=palette)
                 .save(byteio, 'GIF', interlace=False, optimize=True))

                self.gifBuffer.put(
                    (byteio.getvalue(), rawTime, time.time() - startTime))
            except Exception:
                print(traceback.format_exc())
                pass


driver.setLcdMode(0x2, 0x1)
time.sleep(0.2)

for bucket in range(16):
    status = False
    while not status:
        status = driver.deleteBucket(bucket)
        print('Bucket {} deleted: {}'.format(bucket, status))


status = driver.createBucket(0)
print('Bucket {} created: {}'.format(0, status))

# write full black RGBA
driver.writeRGBA(0, [0x0, 0x0, 0x0, 0xff] * (driver._WIDTH * driver._HEIGHT))
driver.write([0x36, 0x01, 0x0])
driver.setLcdMode(0x4, 0x0)

time.sleep(0.2)

paletteLock = Lock()
rawBuffer = queue.Queue(maxsize=2)
gifBuffer = queue.Queue(maxsize=2)
rawProducer = RawProducer(rawBuffer)
gifProducer = GifProducer(rawBuffer, gifBuffer, paletteLock)
rawProducer.start()
gifProducer.start()
frameCount = 0
fps = FPS()
while True:
    try:
        (frame, rawTime, gifTime) = gifBuffer.get()
        startTime = time.time()
        driver.clear()
        driver.writeGIF(0x0, frame)
        driver.setLcdMode(0x5, 0x0)
        writeTime = time.time() - startTime
        print('FPS: {:.1f} - Frame {:5} (size: {:7}) - raw {:.2f}ms, gif {:.2f}ms, write {:.2f}ms  - Palette {}'.format(
            fps(), frameCount, len(frame), rawTime * 1000, gifTime * 1000, writeTime * 1000, palette))

        # dynamiccaly adjust gif color precisione (and size) base on how much 'free time' we have.
        freeTime = (rawTime - writeTime) * 1000

        if freeTime > 5 and palette < 256:
            palette = min(256, math.floor(palette * 1.05))
        if freeTime < -2 and palette > 8:
            palette = max(8, math.floor(palette * 0.95))

        frameCount = frameCount + 1

    except Exception as e:
        traceback.print_exc()
        time.sleep(0.001)
