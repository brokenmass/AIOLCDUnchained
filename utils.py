import threading
import time
import sys
import collections
from threading import Lock, Timer

DEBUG = "--debug" in sys.argv
DEBUG_USB = "--debug-usb" in sys.argv
DEBUG_TIMINGS = "--debug-timings" in sys.argv
DEBUG_Q565 = "--debug-q565" in sys.argv


def debug(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


def debugUsb(*args, **kwargs):
    if DEBUG_USB:
        print(*args, **kwargs)


def debugQ565(*args, **kwargs):
    if DEBUG_Q565:
        print(*args, **kwargs)


timingStack = {}
lock = Lock()


def printTiming(entry):
    def inner(entry, connection, indent="", isLastChild=True):
        header = "┬" if len(entry["childs"]) > 0 else "─"
        tree = indent + connection + header + "─"
        print(
            "{} {} took {:.2f}ms".format(
                tree,
                entry["name"],
                (entry["end"] - entry["start"]) * 1000,
                entry["threadName"],
            )
        )
        for index, child in enumerate(entry["childs"]):
            isChildLastChild = index == (len(entry["childs"]) - 1)
            connection = "└─" if isChildLastChild else "├─"
            nextIndent = "  " if isLastChild else "│ "
            inner(child, connection, indent + nextIndent, isChildLastChild)

    try:
        lock.acquire()
        inner(entry, entry["threadName"][0] + "─")
    finally:
        lock.release()


def timing(func):
    def inner(*args, **kwargs):
        start = time.time()
        threadId = threading.get_ident()
        entry = {
            "threadName": threading.current_thread().name,
            "name": func.__name__,
            "childs": [],
            "start": start,
        }

        if not threadId in timingStack:
            timingStack[threadId] = []
        timingStack[threadId].append(entry)
        res = func(*args, **kwargs)
        entry["end"] = time.time()
        timingStack[threadId].pop()
        if len(timingStack[threadId]) > 0:
            timingStack[threadId][-1]["childs"].append(entry)
        else:
            printTiming(entry)
        return res

    return inner if DEBUG_TIMINGS else func


def debounce(wait):
    def decorator(function):
        timer = None

        def debounced(*args, **kwargs):
            nonlocal timer

            def run():
                nonlocal timer
                timer = None
                return function(*args, **kwargs)

            if timer is not None:
                timer.cancel()

            timer = Timer(wait, run)
            timer.start()

        return debounced

    return decorator


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
    value: float = 0.0

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
