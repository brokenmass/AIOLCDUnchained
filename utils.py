import time
import collections


class LazyHexRepr:
    def __init__(self, data, start=None, end=None, sep=':'):
        self.data = data
        self.start = start
        self.end = end
        self.sep = sep

    def __repr__(self):
        hexvals = map(lambda x: f'{x:02x}', self.data[self.start: self.end])
        return self.sep.join(hexvals)


class FPS:
    def __init__(self, collectionLength=50):
        self.frametimestamps = collections.deque(maxlen=collectionLength)

    def __call__(self):
        self.frametimestamps.append(time.time())
        if (len(self.frametimestamps) > 1):
            return len(self.frametimestamps)/(self.frametimestamps[-1]-self.frametimestamps[0])
        else:
            return 0.0
