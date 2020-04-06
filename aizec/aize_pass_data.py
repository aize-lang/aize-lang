from __future__ import annotations

from typing import *

from aizec.aize_ast import PassData, Source


class PositionData(PassData):
    def __init__(self, source: Source, line_no: int, columns: Tuple[int, int]):
        super().__init__()

        self._source = source
        self._line_no = line_no
        self._columns = columns

    def in_context(self) -> str:
        return f"{self._line_no:>6} | {self._source.lines[self._line_no - 1]}\n" \
               f"         {' ' * self._columns[0]}{'^' * (self._columns[1] - self._columns[0])}"

    def get_source_name(self):
        return self._source.get_name()

    def to(self, other: 'PositionData') -> 'PositionData':
        if self._source is other._source:
            if self._line_no == other._line_no:
                columns = min(self._columns[0], other._columns[0]), max(self._columns[1], other._columns[1])
                return PositionData(self._source, self._line_no, columns)
            else:
                raise ValueError("Not on same line")
        else:
            raise ValueError("Not in same source")

    def __add__(self, other: 'PositionData') -> 'PositionData':
        return self.to(other)

    def subpos(self, start: int, end: int):
        return PositionData(self._source, self._line_no, (self._columns[0] + start, self._columns[0] + end))
