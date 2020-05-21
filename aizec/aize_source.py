from __future__ import annotations

from aizec.common import *


__all__ = ['Source', 'StreamSource', 'FileSource', 'Position', 'TextPosition']


class Source:
    def __init__(self):
        self._lines: List[str] = []

    def add_line(self, line: str):
        self._lines.append(line)

    def get_line(self, index: int) -> str:
        """Return the line indexed by index (starting at 0)"""
        if index < 0:
            raise IndexError(f"Line index must be greater than 0 (got {index})")
        return self._lines[index]

    def read_char(self) -> str:
        """Return the next character of the Source, or an empty string if it is done"""
        raise NotImplementedError()

    def get_unique(self) -> Hashable:
        """Return a unique (hashable) identifier suitable for ensuring no source is parsed multiple times"""
        raise NotImplementedError()

    def get_name(self) -> str:
        """Return a str that is displayed as the source in error messages"""
        raise NotImplementedError()

    def get_path(self) -> Union[Path, None]:
        """Return a Path if this source has a path, or None if it does not"""
        raise NotImplementedError()


class StreamSource(Source):
    def __init__(self, name: str, stream: IO):
        super().__init__()
        self.name = name
        self.stream = stream

    def read_char(self) -> str:
        return self.stream.read(n=1)

    def get_unique(self) -> Hashable:
        return self.name

    def get_name(self) -> str:
        return self.name

    def get_path(self) -> Union[Path, None]:
        return None


class FileSource(Source):
    def __init__(self, path: Path, file_handle: IO):
        super().__init__()
        self.path = path
        self.file_handle = file_handle

    def read_char(self) -> str:
        return self.file_handle.read(1)

    def get_unique(self) -> Hashable:
        return self.path

    def get_name(self) -> str:
        return str(self.path)

    def get_path(self) -> Union[Path, None]:
        return self.path


class Position:
    def get_source_name(self) -> str:
        raise NotImplementedError()

    def __repr__(self) -> str:
        raise NotImplementedError()

    @classmethod
    def new_builtin(cls, builtin_name: str) -> BuiltinPosition:
        return BuiltinPosition(builtin_name)

    @classmethod
    def new_text(cls, source: Source, line: int, columns: Tuple[int, int]) -> TextPosition:
        """
        Return a new Position object for a position in a text source.

        Args:
            source: The Source this Position is in.
            line: The position's line in the file, 1-indexed.
            columns: A Tuple of starting (inclusive) and ending (exclusive) position in the line, 1-indexed
        """
        return TextPosition(source, line, columns)


class BuiltinPosition(Position):
    def __init__(self, builtin_name: str):
        self.builtin_name: str = builtin_name

    def get_source_name(self):
        return self.builtin_name

    def __repr__(self):
        return f"BuiltinPosition()"


class TextPosition(Position):
    def __init__(self, source: Source, line_no: int, columns: Tuple[int, int]):
        self._source = source
        self._line_no = line_no
        self._columns = columns

    def in_context(self) -> str:
        line = self._source.get_line(self._line_no - 1)
        if not (1 <= (self._columns[1]-1) <= len(line)):
            raise IndexError("End column must be valid")
        if not (1 <= self._columns[0] < self._columns[1]):
            raise IndexError("Start column must be valid")
        return f"{self._line_no:>6} | {line}\n" \
               f"         {' ' * (self._columns[0]-1)}{'^' * (self._columns[1] - self._columns[0])}"

    def get_source_name(self):
        return self._source.get_name()

    def to(self, other: TextPosition) -> TextPosition:
        if self._source is other._source:
            if self._line_no == other._line_no:
                columns = min(self._columns[0], other._columns[0]), max(self._columns[1], other._columns[1])
                return TextPosition(self._source, self._line_no, columns)
            else:
                raise ValueError("Not on same line")
        else:
            raise ValueError("Not in same source")

    def __add__(self, other: TextPosition) -> TextPosition:
        return self.to(other)

    def __repr__(self):
        return f"TextPosition(line={self._line_no}, columns={self._columns})"
