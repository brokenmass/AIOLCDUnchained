from dataclasses import dataclass, field
from typing import Dict, Optional

from PIL import Image

from utils import debugQ565, timing

Q565_OP_INDEX = 0b0000_0000

Q565_OP_DIFF = 0b0100_0000

Q565_OP_LUMA = 0b1000_0000
Q565_OP_DIFF_INDEXED = 0b1010_0000

Q565_OP_RUN = 0b1100_0000
Q565_OP_RGB565 = 0b1111_1110
Q565_OP_END = 0b1111_1111

Q565_MASK_2 = 0b1100_0000
Q565_MASK_3 = 0b1110_0000


Q565_MAGIC = ord("q") << 24 | ord("5") << 16 | ord("6") << 8 | ord("5")


@dataclass
class Pixel:
    px_bytes: bytearray = field(init=False)

    def __post_init__(self):
        self.px_bytes = bytearray((0, 0))

    def setBytes(self, values: bytes) -> None:
        if len(values) != 2:
            raise ValueError("a tuple of 2 values should be provided")

        self.px_bytes[0:2] = values

    def setRGB565(self, values: tuple):
        data = values[0] << 11 | values[1] << 5 | values[2]
        self.px_bytes[0:2] = data.to_bytes(2, "big")

    def __str__(self) -> str:
        r, g, b = self.RGB565
        return f"R: {r} G: {g} B: {b}"

    def smallDiff(self, diff):
        rDiff = ((diff >> 4) & 0b11) - 2
        gDiff = ((diff >> 2) & 0b11) - 2
        bDiff = (diff & 0b11) - 2

        self.applyDiff((rDiff, gDiff, bDiff))

    def largeDiff(self, diff1, diff2):
        gDiff = (diff1 & 0b0001_1111) - 16
        rDiff = ((diff2 >> 4) & 0x0F) - 8 + gDiff
        bDiff = (diff2 & 0x0F) - 8 + gDiff

        self.applyDiff((rDiff, gDiff, bDiff))

    def indexedDiff(self, diff1, diff2):
        gDiff = ((diff1 & 0b0001_1100) >> 2) - 4
        rDiff = (diff1 & 0b0000_0011) - 2
        bDiff = (diff2 >> 6) - 2

        self.applyDiff((rDiff, gDiff, bDiff))

    def applyDiff(self, diffs):
        rDiff, gDiff, bDiff = diffs
        r, g, b = self.RGB565
        before = self.int
        red = (r + rDiff) & 0b1_1111
        green = (g + gDiff) & 0b11_1111
        blue = (b + bDiff) & 0b1_1111
        self.setRGB565((red, green, blue))
        debugQ565(
            "    before {} - diff [{} {} {}] - after {}".format(
                before, *diffs, self.int
            )
        )

    @property
    def int(self):
        return self.px_bytes[0] << 8 | self.px_bytes[1]

    @property
    def RGB565(self):
        data = self.px_bytes[0] << 8 | self.px_bytes[1]
        r = (data & 0b1111_1000_0000_0000) >> 11
        g = (data & 0b0000_0111_1110_0000) >> 5
        b = data & 0b0000_0000_0001_1111
        return (r, g, b)

    @property
    def RGB888(self):
        r, g, b = self.RGB565
        r8 = (r * 527 + 23) >> 6
        g8 = (g * 259 + 33) >> 6
        b8 = (b * 527 + 23) >> 6

        return (r8, g8, b8)

    @property
    def bytes(self) -> bytes:
        return bytes(self.px_bytes)

    @property
    def hash(self) -> int:
        return (self.px_bytes[0] + self.px_bytes[1]) & 0b0011_1111


class ByteWriter:
    def __init__(self, size: int):
        self.bytes = bytearray(size)
        self.write_pos = 0

    def write(self, byte: int):
        self.bytes[self.write_pos] = byte % 256
        self.write_pos += 1

    def output(self):
        return bytes(self.bytes[0 : self.write_pos])


class ByteReader:
    def __init__(self, data: bytes):
        self.bytes = data
        self.read_pos = 0
        self.max_pos = len(self.bytes)

    def read(self) -> Optional[int]:
        if self.read_pos >= self.max_pos:
            return None

        out = self.bytes[self.read_pos]
        self.read_pos += 1
        return out

    @timing
    def output(self):
        return bytes(self.bytes[0 : self.read_pos])


@timing
def encode_img(img: Image.Image) -> bytes:
    width, height = img.size
    img_bytes = img.tobytes()
    return encode(img_bytes, width, height)


@timing
def decode_to_img(img_bytes: bytes) -> Image.Image:
    out = decode(img_bytes)

    size = (out["width"], out["height"])
    return Image.frombuffer(out["channels"], size, bytes(out["bytes"]), "raw")


def write_32_bits(value: int, writer: ByteWriter) -> None:
    writer.write((0xFF000000 & value) >> 24)
    writer.write((0x00FF0000 & value) >> 16)
    writer.write((0x0000FF00 & value) >> 8)
    writer.write((0x000000FF & value))


def read_32_bits(reader: ByteReader) -> int:
    data = [reader.read() for _ in range(4)]
    b1, b2, b3, b4 = data
    return b1 << 24 | b2 << 16 | b3 << 8 | b4


def write_16_bits(value: bytes, writer: ByteWriter) -> None:
    writer.write(value[0])
    writer.write(value[1])


def read_16_bits(reader: ByteReader) -> int:
    data = [reader.read() for _ in range(2)]
    b1, b2 = data
    return b2 << 8 | b1


@timing
def encode(img_bytes: bytes, width: int, height: int):
    total_size = height * width
    channels = 3
    pixel_data = (
        img_bytes[i : i + channels] for i in range(0, len(img_bytes), channels)
    )
    max_n_bytes = 6 + total_size * 3 + 1  # header + max 3 bytes per pixel + end
    writer = ByteWriter(max_n_bytes)
    hash_array = [Pixel() for _ in range(64)]
    for px in hash_array:
        px.setBytes(bytearray((0, 0)))

    # write header
    write_32_bits(Q565_MAGIC, writer)
    write_16_bits(width.to_bytes(2, "little"), writer)
    write_16_bits(height.to_bytes(2, "little"), writer)

    # encode pixels

    @timing
    def loop():
        run = 0
        prev_px_value = Pixel()
        px_value = Pixel()
        for i, px in enumerate(pixel_data):
            prev_px_value.setBytes(px_value.bytes)

            r = (px[0] * 249 + 1014) >> 11
            g = (px[1] * 253 + 505) >> 10
            b = (px[2] * 249 + 1014) >> 11

            px_value.setRGB565((r, g, b))

            if px_value == prev_px_value:
                run += 1
                if run == 62 or (i + 1) >= total_size:
                    writer.write(Q565_OP_RUN | (run - 1))
                    run = 0
                continue

            if run:
                writer.write(Q565_OP_RUN | (run - 1))
                run = 0

            index_pos = px_value.hash
            if hash_array[index_pos] == px_value:
                writer.write(Q565_OP_INDEX | index_pos)
                continue

            prevR, prevG, prevB = prev_px_value.RGB565

            rDiff = (r - prevR) & 0b1_1111
            gDiff = (g - prevG) & 0b11_1111
            bDiff = (b - prevB) & 0b1_1111

            if all(-2 <= x <= 1 for x in (rDiff, gDiff, bDiff)):
                writer.write(
                    Q565_OP_DIFF | (rDiff + 2) << 4 | (gDiff + 2) << 2 | (bDiff + 2)
                )
                continue

            rgDiff = rDiff - gDiff
            bgDiff = bDiff - gDiff

            if all(-8 <= x <= 7 for x in (rgDiff, bgDiff)) and -16 <= gDiff <= 15:
                writer.write(Q565_OP_LUMA | (gDiff + 16))
                writer.write((rgDiff + 8) << 4 | (bgDiff + 8))

            # TODO: OP_DIFF_INDEXED
            else:
                writer.write(Q565_OP_RGB565)
                writer.write(px_value.px_bytes[1])
                writer.write(px_value.px_bytes[0])

            hash_array[px_value.hash].setBytes(px_value.bytes)

    loop()
    writer.write(Q565_OP_END)
    return writer.output()


def writePixel(buffer, index, pixel):
    end = index + 3
    buffer[index:end] = pixel.RGB888
    return end


def writeMany(buffer, index, pixel, count):
    end = index
    while count > 0:
        end = writePixel(buffer, end, pixel)
        count -= 1
    return end


def decode(file_bytes: bytes) -> Dict:
    reader = ByteReader(file_bytes)
    header_magic = read_32_bits(reader)
    if header_magic != Q565_MAGIC:
        raise ValueError("provided image does not contain QOI header")

    width = read_16_bits(reader)
    height = read_16_bits(reader)
    channels = 3

    hash_array = [Pixel() for _ in range(64)]
    for px in hash_array:
        px.setBytes(bytearray((0, 0)))
    out_size = width * height * channels
    pixel_data = bytearray(out_size)
    px_value = Pixel()
    index = 0
    op = 0
    while True:
        op += 1
        b1 = reader.read()
        if b1 is None:
            break
        updatePalette = True
        debugQ565("\n")
        if b1 == Q565_OP_END:
            debugQ565("{} {} - Q565_OP_END".format(op, b1))
            break

        elif b1 == Q565_OP_RGB565:
            debugQ565("{} {} - Q565_OP_RGB565".format(op, b1))
            b2, b3 = (reader.read(), reader.read())
            px_value.setBytes((b3, b2))
            debugQ565("[{} {}] {}".format(b2, b3, px_value.int))

        elif (b1 & Q565_MASK_2) == Q565_OP_RUN:
            count = (b1 & 0b0011_1111) + 1
            debugQ565("{} {} - Q565_OP_RUN {}".format(op, b1, count))
            updatePalette = False
            index = writeMany(pixel_data, index, px_value, count)
            continue

        elif (b1 & Q565_MASK_2) == Q565_OP_INDEX:
            debugQ565("{} {} - Q565_OP_INDEX".format(op, b1))
            px_value.setBytes(hash_array[b1].bytes)
            updatePalette = False

        elif (b1 & Q565_MASK_2) == Q565_OP_DIFF:
            debugQ565("{} {} - Q565_OP_DIFF".format(op, b1))
            px_value.smallDiff(b1)
            updatePalette = False

        elif (b1 & Q565_MASK_3) == Q565_OP_LUMA:
            debugQ565("{} {} - Q565_OP_LUMA".format(op, b1))
            b2 = reader.read()
            px_value.largeDiff(b1, b2)

        elif (b1 & Q565_MASK_3) == Q565_OP_DIFF_INDEXED:
            debugQ565("{} {} - Q565_OP_DIFF_INDEXED".format(op, b1))
            b2 = reader.read()
            px_value.setBytes(hash_array[b2 & 0b0011_1111].bytes)
            px_value.indexedDiff(b1, b2)

        else:
            raise "UNRECOGNISED COMMAND"

        if updatePalette:
            debugQ565("    HASH:", px_value.hash)
            hash_array[px_value.hash].setBytes(px_value.bytes)

        index = writePixel(pixel_data, index, px_value)

    out = {
        "width": width,
        "height": height,
        "channels": "RGB",
        "colorspace": 1,
        "bytes": pixel_data,
    }

    return out
