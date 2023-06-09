import time
import driver
import time
import queue
from threading import Thread
from utils import FPS, debug


class FrameWriter(Thread):
    def __init__(self, frameBuffer: queue.Queue, lcd: driver.KrakenLCD):
        Thread.__init__(self, name="FrameWriter")
        self.daemon = True
        self.shouldStop = False
        self.frameBuffer = frameBuffer
        self.frameCount = 0
        self.lcd = lcd
        self.lastDataTime = 0
        self.fps = FPS()

    def run(self):
        debug("Frame writer started")
        while not self.shouldStop:
            if self.frameBuffer.empty():
                time.sleep(0.001)
                continue

            self.onFrame()

    def onFrame(self):
        (frame, rawTime, gifTime) = self.frameBuffer.get()

        startTime = time.time()
        self.lcd.writeFrame(frame)
        writeTime = time.time() - startTime
        freeTime = rawTime - writeTime

        debug(
            "FPS: {:4.1f} - Frame {:5} (size: {:7}) - raw {:6.2f}ms, gif {:6.2f}ms, write {:6.2f}ms, free time {: 7.2f}ms ".format(
                self.fps(),
                self.frameCount,
                len(frame),
                rawTime * 1000,
                gifTime * 1000,
                writeTime * 1000,
                freeTime * 1000,
            )
        )
        self.frameCount += 1
