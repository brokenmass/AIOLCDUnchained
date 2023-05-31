import time
import sys
import collections

DEBUG = "--debug" in sys.argv
DEBUG_TIMINGS = "--debug-timings" in sys.argv


def debug(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


def timing(func):
    def inner(*args, **kwargs):
        start = time.time()
        res = func(*args, **kwargs)
        print("{} took {:.2f}ms".format(func.__name__, (time.time() - start) * 1000))

        return res

    return inner if DEBUG_TIMINGS else func


class LazyHexRepr:
    def __init__(self, data, start=None, end=None, sep=":"):
        self.data = data
        self.start = start
        self.end = end
        self.sep = sep

    def __repr__(self):
        hexvals = map(lambda x: f"{x:02x}", self.data[self.start : self.end])
        return self.sep.join(hexvals)


class FPS:
    value: float

    def __init__(self, collectionLength=50):
        self.frametimestamps = collections.deque(maxlen=collectionLength)

    def __call__(self):
        self.frametimestamps.append(time.time())
        if len(self.frametimestamps) > 1:
            self.value = len(self.frametimestamps) / (
                self.frametimestamps[-1] - self.frametimestamps[0]
            )
        else:
            self.value = 0.0

        return self.value
