import time
import driver
import time
from PIL import Image
from io import BytesIO
from mss import mss
import queue
from threading import Thread, Event
from utils import FPS

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
driver.writeRGBA(0, [0x0, 0x0, 0x0, 0xff] * (driver._WIDTH * driver._HEIGHT))
driver.setLcdMode(0x4, 0x0)

time.sleep(0.2)


class RawProducer(Thread):
    def __init__(self, rawBuffer: queue.Queue):
        Thread.__init__(self)
        self.daemon = True
        self.rawBuffer = rawBuffer

    def run(self):
        print("Screencap worker started")
        sct = mss()
        frameCount = 0
        while True:
            if self.rawBuffer.full():
                time.sleep(0.005)
                continue
            startTime = time.time()
            screenshot = sct.grab(
                {'top': 500, 'left': 500, 'width': driver._WIDTH, 'height': driver._HEIGHT})

            self.rawBuffer.put((screenshot, time.time() - startTime))
            frameCount += 1


class GifProducer(Thread):
    def __init__(self, rawBuffer: queue.Queue, gifBuffer: queue.Queue):
        Thread.__init__(self)
        self.daemon = True
        self.rawBuffer = rawBuffer
        self.gifBuffer = gifBuffer

    def run(self):
        print("Gif converter worker started")
        sct = mss()
        frameCount = 0
        while True:
            if self.gifBuffer.full():
                time.sleep(0.005)
                continue

            (screenshot, rawTime) = self.rawBuffer.get()
            startTime = time.time()
            img = Image.frombytes(
                'RGB',
                (screenshot.width, screenshot.height),
                screenshot.rgb,
            ).convert('P', palette=Image.Palette.ADAPTIVE, colors=64)
            byteio = BytesIO()
            img.save(byteio, 'GIF', interlace=False, optimize=True)

            self.gifBuffer.put(
                (byteio.getvalue(), rawTime, time.time() - startTime))
            frameCount += 1


rawBuffer = queue.Queue(maxsize=2)
gifBuffer = queue.Queue(maxsize=2)

rawProducer = RawProducer(rawBuffer)
gifProducer = GifProducer(rawBuffer, gifBuffer)
rawProducer.start()
gifProducer.start()
frameCount = 0
fps = FPS()
while True:

    (frame, rawTime, gifTime) = gifBuffer.get()
    startTime = time.time()
    driver.clear()
    driver.writeGIF(0x0, frame)
    driver.setLcdMode(0x5, 0x0)
    writeTime = time.time() - startTime
    print("FPS: {:.1f} - Frame {:5} (size: {:7}) - raw {:.2f}ms, gif {:.2f}ms, write {:.2f}ms  - ".format(
        fps(), frameCount, len(frame), rawTime * 1000, gifTime * 1000, writeTime * 1000))
    frameCount = frameCount + 1
