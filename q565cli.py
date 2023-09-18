from q565 import encode_img, decode_to_img
from PIL import Image
import sys


def replace_extension(path: str, extension: str) -> str:
    old_extension = path.split(".")[-1]
    new_path = path.replace("." + old_extension, "." + extension)
    return new_path


def main():
    encode = "--encode" in sys.argv
    decode = "--decode" in sys.argv
    file_path = sys.argv[1]
    if encode:
        try:
            img = Image.open(file_path)
        except Exception as exc:
            print(f"image load failed: {exc}")
            return

        out_path = replace_extension(file_path, "q565")
        output = encode_img(img)
        with open(out_path, "wb") as qoiFile:
            qoiFile.write(output)

    if decode:
        with open(file_path, "rb") as qoiFile:
            file_bytes = qoiFile.read()

        out_path = replace_extension(file_path, "png")
        img = decode_to_img(file_bytes)
        img.save(out_path, "png")


if __name__ == "__main__":
    main()
