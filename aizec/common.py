from __future__ import annotations

from typing import *
from pathlib import Path


class Trie:
    def __init__(self, char: str, children: Dict[str, Trie], is_leaf: bool):
        self.char = char
        self.children = children
        self.is_leaf = is_leaf

    @classmethod
    def from_list(cls, strs: List[str]) -> Trie:
        root = Trie("", {}, is_leaf=False)
        for item in strs:
            trie = root
            for char in item:
                if char in trie.children:
                    trie = trie.children[char]
                else:
                    trie.children[char] = Trie(char, {}, False)
                    trie = trie.children[char]
            trie.is_leaf = True
        return root
