import time
import driver
from PIL import Image, ImageDraw
from io import BytesIO
import queue
import colorsys
from threading import Thread, Event
from utils import FPS
from mss import mss
from utils import FPS, debug
from workers import FrameWriter


lcd = driver.KrakenLCD()
lcd.setupStream()


class FrameProducer(Thread):
    def __init__(self, frameBuffer: queue.Queue):
        Thread.__init__(self)
        self.daemon = True
        self.frameBuffer = frameBuffer

    def hsv2rgb(self, h, s, v):
        return tuple(round(i * 255) for i in colorsys.hsv_to_rgb(h, s, v))

    def run(self):
        print("Frame generator worker started")
        frameCount = 0
        while True:
            if self.frameBuffer.full():
                time.sleep(0.001)
                continue
            startTime = time.time()
            color = self.hsv2rgb(((5 * frameCount) % 360) / 360, 1, 1)
            img = Image.new("RGB", lcd.resolution)
            draw = ImageDraw.Draw(img)
            draw.rectangle(
                [(0, 0), (lcd.resolution.width // 2, lcd.resolution.height // 2)],
                fill=color,
            )
            draw.rectangle(
                [
                    (lcd.resolution.width // 2, lcd.resolution.height // 2),
                    (lcd.resolution.width, lcd.resolution.height),
                ],
                fill=color,
            )

            img = img.rotate(frameCount * 2)

            self.frameBuffer.put(
                (lcd.imageToFrame(img, adaptive=True), 0, time.time() - startTime)
            )
            frameCount += 1


frameBuffer = queue.Queue(maxsize=1)

frameProducer = FrameProducer(frameBuffer)
frameWriter = FrameWriter(frameBuffer, lcd)

frameProducer.start()
frameWriter.start()

print("SignalRGB rotating demo started")

try:
    while True:
        time.sleep(1)
        if not (frameProducer.is_alive() and frameWriter.is_alive()):
            raise KeyboardInterrupt("Some thread is dead")
except KeyboardInterrupt:
    frameWriter.shouldStop = True
    frameWriter.join()
    exit()
