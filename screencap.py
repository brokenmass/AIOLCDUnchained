import time
import driver
import time
from PIL import Image
from mss import mss
import queue
from threading import Thread
from utils import debug
import driver
from workers import FrameWriter


lcd = driver.KrakenLCD()
lcd.setupStream()


class RawProducer(Thread):
    def __init__(self, rawBuffer: queue.Queue):
        Thread.__init__(self)
        self.daemon = True
        self.rawBuffer = rawBuffer

    def run(self):
        debug("Screencap worker started")
        sct = mss()
        while True:
            if self.rawBuffer.full():
                time.sleep(0.005)
                continue
            startTime = time.time()
            screenshot = sct.grab(
                {
                    "top": 500,
                    "left": 500,
                    "width": lcd.resolution.width,
                    "height": lcd.resolution.height,
                }
            )

            self.rawBuffer.put((screenshot, time.time() - startTime))


class FrameProducer(Thread):
    def __init__(self, rawBuffer: queue.Queue, frameBuffer: queue.Queue):
        Thread.__init__(self)
        self.daemon = True
        self.rawBuffer = rawBuffer
        self.frameBuffer = frameBuffer

    def run(self):
        print("Image converter worker started")
        while True:
            if self.frameBuffer.full():
                time.sleep(0.001)
                continue

            (screenshot, rawTime) = self.rawBuffer.get()
            startTime = time.time()
            img = Image.frombytes(
                "RGB",
                (screenshot.width, screenshot.height),
                screenshot.rgb,
            )

            self.frameBuffer.put(
                (lcd.imageToFrame(img, adaptive=True), rawTime, time.time() - startTime)
            )


rawBuffer = queue.Queue(maxsize=1)
frameBuffer = queue.Queue(maxsize=1)

rawProducer = RawProducer(rawBuffer)
frameProducer = FrameProducer(rawBuffer, frameBuffer)
frameWriter = FrameWriter(frameBuffer, lcd)

rawProducer.start()
frameProducer.start()
frameWriter.start()

print("SignalRGB screencap demo started")

try:
    while True:
        time.sleep(1)
        if not (
            rawProducer.is_alive()
            and frameProducer.is_alive()
            and frameWriter.is_alive()
        ):
            raise KeyboardInterrupt("Some thread is dead")
except KeyboardInterrupt:
    frameWriter.shouldStop = True
    frameWriter.join()
    exit()
