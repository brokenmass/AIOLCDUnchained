from io import BytesIO
import time
import driver
import time
import sys
from PIL import Image, ImageSequence

if len(sys.argv) < 3:
    print("Usage: python ./writeGif.py /path/to/your/file.gif <rotation 0|90|180|270>")
    exit()


def sizeof_fmt(num, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


lcd = driver.KrakenLCD()

MIN_COLORS = 16
rotation = int(sys.argv[2])

gifData = None
found = False
iteration = 0

colorBoundary = [MIN_COLORS, 256]
iteration = 0
previousRun = (0, 0)
img = Image.open(sys.argv[1])
while not found:
    colors = colorBoundary[0] + (colorBoundary[1] - colorBoundary[0]) // 2

    byteio = BytesIO()
    # Get sequence iterator
    frames = ImageSequence.Iterator(img)
    newFrames = []
    for frame in frames:
        frame = frame.convert("RGB").rotate(rotation)
        pal = frame.quantize(colors)
        newFrame = frame.quantize(
            colors, palette=pal, dither=Image.FLOYDSTEINBERG
        ).resize(
            lcd.resolution,
            Image.Resampling.LANCZOS,
        )
        newFrames.append(newFrame)

    om = newFrames[0]
    om.info = img.info  # Copy sequence info
    om.save(
        byteio,
        "GIF",
        interlace=False,
        optimize=True,
        save_all=True,
        append_images=newFrames,
    )
    gifData = byteio.getvalue()
    gifSize = len(gifData)
    print(
        "Iteration {:2}: {} colors size {}, {}".format(
            iteration + 1, colors, sizeof_fmt(gifSize), colorBoundary
        )
    )
    iteration = +1

    if gifSize > lcd.maxBucketSize:
        colorBoundary[1] = colors
    else:
        colorBoundary[0] = colors
        # no size increase despite color increase, we can stop
        if (previousRun[0] <= colors and previousRun[1] == gifSize) or (
            colorBoundary[1] - colorBoundary[0] < 10
        ):
            print("found")
            found = True
    previousRun = (colors, gifSize)
    if iteration == 20:
        exit(1)

lcd.setLcdMode(driver.DISPLAY_MODE.LIQUID, 0x0)
time.sleep(0.1)
lcd.deleteAllBuckets()
lcd.createBucket(0, size=len(gifData))


lcd.writeGIF(gifData, 0, fast=False)
lcd.setLcdMode(0x4, 0x0)
