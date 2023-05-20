import time
import driver
import time
from PIL import Image
from io import BytesIO
from mss import mss
import queue
from threading import Thread, Event

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
driver.write([0x36, 0x01, 0x0])
driver.setLcdMode(0x4, 0x0)

time.sleep(0.2)


class Producer(Thread):

    def __init__(self, stopEvent: Event, buffer: queue.Queue):
        Thread.__init__(self)
        self.stopEvent = stopEvent
        self.buffer = buffer

    def run(self):
        print("Screencap worker started")
        sct = mss()
        frameCount = 0
        while not self.stopEvent.is_set():
            if self.buffer.full():
                time.sleep(0.005)
                continue
            screenshot = sct.grab({'top': 500, 'left': 500, 'width': driver._WIDTH, 'height': driver._HEIGHT})
            img = Image.frombytes(
                'RGB',
                (screenshot.width, screenshot.height),
                screenshot.rgb,
            )
            byteio = BytesIO()
            img.save(byteio, 'GIF', interlace=False, optimize=True)
            self.buffer.put(byteio.getvalue())
            frameCount += 1

try:
    buffer = queue.Queue(maxsize=2)
    event = Event()
    producer = Producer(event, buffer)
    producer.start()
    frameCount = 0
    while True:
        startTime = time.time()
        frame = buffer.get()

        driver.clear()
        driver.writeGIF(0x0, frame)
        driver.setLcdMode(0x5, 0x0)

        print("Frame {} (size: {}) took: {} ".format(frameCount, len(frame), time.time() - startTime))
        frameCount = frameCount + 1
except KeyboardInterrupt:
    print("Stopping threads")
    event.set()
finally:
    print("Exit")




