"""A dict that evicts its least-recently-used entry past a ceiling.

Every map in this process that grows with traffic is bounded by this one class rather than
by a mechanism each: an unbounded map was the dominant source of memory growth here once,
and the session caches were the ones that showed it.
"""

from __future__ import annotations

from collections import OrderedDict


class LRUDict(OrderedDict):
    def __init__(self, maxlen: int) -> None:
        super().__init__()
        self._maxlen = max(1, maxlen)

    def __setitem__(self, key, value) -> None:
        super().__setitem__(key, value)
        self.move_to_end(key)
        while len(self) > self._maxlen:
            self.popitem(last=False)

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default
