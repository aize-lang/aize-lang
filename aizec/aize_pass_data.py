from __future__ import annotations

from typing import *

from aizec.aize_ast import PassData, Source


class PositionData(PassData):
    def __init__(self, source: Source, line_no: int, columns: Tuple[int, int]):
        super().__init__()

        self.source = source
        self.line_no = line_no
        self.columns = columns

    def in_context(self) -> str:
        return f"{self.line_no:>6} | {self.source.lines[self.line_no-1]}\n" \
               f"         {' ' * self.columns[0]}{'^'*(self.columns[1]-self.columns[0])}"

    def to(self, other: 'PositionData') -> 'PositionData':
        if self.source is other.source:
            if self.line_no == other.line_no:
                columns = min(self.columns[0], other.columns[0]), max(self.columns[1], other.columns[1])
                return PositionData(self.source, self.line_no, columns)
            else:
                raise ValueError("Not on same line")
        else:
            raise ValueError("Not in same source")

    def __add__(self, other: 'PositionData') -> 'PositionData':
        return self.to(other)

    def subpos(self, start: int, end: int):
        return PositionData(self.source, self.line_no, (self.columns[0] + start, self.columns[0] + end))
