from typing import List, Tuple, Dict, Type as Cls, TypeVar, IO, Union
from pathlib import Path

T = TypeVar('T')


def new(cls: Cls[T]) -> T:
    return cls.__new__(cls)


def static_var(**kw_vars):
    def _dec(func):
        def wrapped(*args, **kwargs):
            func(*args, **kwargs)
        return func
    return _dec


class AizeError(Exception):
    def display(self, file: IO):
        raise NotImplementedError()


class TextPos:
    def __init__(self, text: str, line: int, pos: Tuple[int, int], file: Path):
        self.text = text
        self.line = line
        self.pos = pos
        self.file = file

    def get_line(self):
        return self.text.splitlines()[self.line-1]

    def __repr__(self):
        return f"TextPos({self.text!r}, {self.line}, {self.pos})"


STD = Path(__file__).absolute().parent.parent / "std"
