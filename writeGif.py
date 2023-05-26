import time
import driver
import time
import sys


if (len(sys.argv) < 2):
    print("Usage: python ./writeGif.py /path/to/your/file.gif")
    exit()

file = open(sys.argv[1], "rb")
gifData = file.read()
file.close()
driver.setLcdMode(0x2, 0x1)
time.sleep(0.2)


for bucket in range(16):
    status = False
    while not status:
        status = driver.deleteBucket(bucket)
        print("Bucket {} deleted: {}".format(bucket, status))

status = driver.createBucket(0, size=len(gifData))
print("Bucket {} created: {}".format(0, status))


driver.writeGIF(0, gifData, fast=False)
driver.setLcdMode(0x4, 0x0)
