from typing import Tuple

from aizec.aize_ast import PassData, Source


class NodePosition(PassData):
    def __init__(self, source: Source, line_no: int, columns: Tuple[int, int]):
        super().__init__()

        self.source = source
        self.line_no = line_no
        self.columns = columns

    def in_context(self) -> str:
        return f"{self.line_no:>6} | {self.source.lines[self.line_no-1]}\n" \
               f"         {' ' * self.columns[0]}{'^'*(self.columns[1]-self.columns[0])}"

    def to(self, other: 'NodePosition') -> 'NodePosition':
        if self.source is other.source:
            if self.line_no == other.line_no:
                columns = min(self.columns[0], other.columns[0]), max(self.columns[1], other.columns[1])
                return NodePosition(self.source, self.line_no, columns)
            else:
                raise ValueError("Not on same line")
        else:
            raise ValueError("Not in same source")


class EmptyPassData(PassData):
    def __init__(self):
        super().__init__()