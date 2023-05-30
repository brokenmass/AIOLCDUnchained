# Kraken Elite LCD playground

WARNING: i'm not responsible for any damege to your equipment. If anything get stuck your best option is to turn off your pc and disconnect it from power for a minute or two before restarting it.

# Installation

checkout the repository or download the latest code and install python dependencies

```
pip install --upgrade hidapi mss pillow winusbcdc>=1.5 libusb-package psutil
```

## Usage

Ensure NZXT CAM is closed and start one of the available functions:

### Write GIF demo:

Writes a gif (static or animated) to the device

```
python writeGif.py path/to/your/file.gif
```

### Rotating demo:

Simple animation with frames generated in realtime:

```
python rotating.py
```

### Screencap demo:

Captures an area of your screen and renders it in the kraken elit lcd

```
python screencap.py
```

### Signalrgb demo:

WORK IN PROGRESS

You need to extract GothamBold.ttf font from the package available https://freefontsfamily.com/gotham-font-family/ into this project folder

Receives a canvas section from signalRGB, adds temperature infos and display it on the device

```
python server.py
```

## License

MIT License

Copyright (c) 2023 Marco Massarotto

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
