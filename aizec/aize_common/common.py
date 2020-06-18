from __future__ import annotations

from typing import *
from contextlib import contextmanager
from functools import reduce
from abc import ABC, abstractmethod
# from dataclasses import dataclass
from pathlib import Path


class Trie:
    def __init__(self, char: str, children: Dict[str, Trie], is_leaf: bool):
        self.char: str = char
        self.children: Dict[str, Trie] = children
        self.is_leaf: bool = is_leaf

    @classmethod
    def from_list(cls, strs: List[str]) -> Trie:
        root: Trie = Trie("", {}, is_leaf=False)
        for item in strs:
            trie: Trie = root
            for char in item:
                if char in trie.children:
                    trie = trie.children[char]
                else:
                    trie.children[char] = Trie(char, {}, False)
                    trie = trie.children[char]
            trie.is_leaf = True
        return root


def all_subclasses(cls: type) -> Set[type]:
    from functools import reduce
    from operator import or_

    return reduce(or_, map(all_subclasses, cls.__subclasses__()), set(cls.__subclasses__()))
