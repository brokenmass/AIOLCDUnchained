import time
import driver
import time
from PIL import Image, ImageDraw
from io import BytesIO
import queue
import colorsys
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

time.sleep(0.5)


class Producer(Thread):
    def __init__(self, buffer: queue.Queue):
        Thread.__init__(self)
        self.daemon = True
        self.buffer = buffer

    def hsv2rgb(self, h, s, v):
        return tuple(round(i * 255) for i in colorsys.hsv_to_rgb(h, s, v))

    def run(self):
        print("Frame generator worker started")
        frameCount = 0
        while True:
            if self.buffer.full():
                time.sleep(0.001)
                continue
            startTime = time.time()
            color = self.hsv2rgb(((5*frameCount) % 360) / 360, 1, 1)
            img = Image.new("RGB", (driver._WIDTH, driver._HEIGHT))
            draw = ImageDraw.Draw(img)
            draw.rectangle(
                [(0, 0), (driver._WIDTH/2, driver._HEIGHT / 2)], fill=color)
            draw.rectangle([(driver._WIDTH/2, driver._HEIGHT / 2),
                           (driver._WIDTH, driver._HEIGHT)], fill=color)

            img = img.rotate(frameCount * 2)
            byteio = BytesIO()
            img.save(byteio, 'GIF', interlace=False, optimize=True)
            self.buffer.put((byteio.getvalue(), time.time() - startTime))
            frameCount += 1


buffer = queue.Queue(maxsize=2)
producer = Producer(buffer)
producer.start()
frameCount = 0
fps = FPS()
first = True
while True:
    (frame, drawTime) = buffer.get()
    startTime = time.time()
    driver.clear()
    driver.writeGIF(0x0, frame, fast=True)

    driver.setLcdMode(0x5, 0x0)
    writeTime = time.time() - startTime
    print("FPS: {:.1f} - Frame {:5} (size: {:7}) - draw {:.2f}ms, write {:.2f}ms  - ".format(
        fps(), frameCount, len(frame), drawTime * 1000, writeTime * 1000))
    frameCount = frameCount + 1
