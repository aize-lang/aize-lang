from typing import List, Tuple, Dict, Type as Cls, TypeVar, IO
from pathlib import Path

T = TypeVar('T')


def new(cls: Cls[T]) -> T:
    return cls.__new__(cls)


class AizeError(Exception):
    def display(self, file: IO):
        raise NotImplementedError()


class TextPos:
    def __init__(self, text: str, line: int, pos: Tuple[int, int], file: Path):
        self.text = text
        self.line = line
        self.pos = pos
        self.file = file

    def __repr__(self):
        return f"TextPos({self.text!r}, {self.line}, {self.pos})"
