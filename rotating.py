import time
import driver
import time
from PIL import Image, ImageDraw
from io import BytesIO
import queue
import colorsys
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
    def hsv2rgb(self, h,s,v):
        return tuple(round(i * 255) for i in colorsys.hsv_to_rgb(h,s,v))
    def run(self):
        print("Screencap worker started")
        frameCount = 0
        while not self.stopEvent.is_set():
            if self.buffer.full():
                time.sleep(0.001)
                continue
            color = self.hsv2rgb(((5*frameCount) %360) / 360, 1, 1)
            img = Image.new("RGB", (driver._WIDTH, driver._HEIGHT))
            draw = ImageDraw.Draw(img)
            draw.rectangle([(0,0), (driver._WIDTH/2, driver._HEIGHT /2)], fill = color )
            draw.rectangle([(driver._WIDTH/2, driver._HEIGHT /2), (driver._WIDTH,driver._HEIGHT)], fill = color )

            img = img.rotate(frameCount * 2)
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

        print("Frame {:5} took {:.2f}ms (size: {:7})".format(frameCount, (time.time() - startTime)*1000, len(frame)))
        frameCount = frameCount + 1
except KeyboardInterrupt:
    print("Stopping threads")
    event.set()
finally:
    print("Exit")




