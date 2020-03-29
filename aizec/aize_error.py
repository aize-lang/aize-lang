import sys
import contextlib
from typing import List, IO

from aizec.aize_pass_data import PositionData


class Reporter:
    def __init__(self, io: IO):
        self._io = io

        self._indent_level = 0

    def positioned_error(self, type: str, source: str, pos: PositionData, msg: str):
        self.write(f"In {source}:")
        self.write(f"{type}: {msg}:")
        self.write(f"{pos.in_context()}")

    def source_error(self, type: str, source_name: str, msg: str):
        self.write(f"For {source_name}:")
        self.write(f"{type}: {msg}.")

    @contextlib.contextmanager
    def indent(self):
        self._indent_level += 1
        yield
        self._indent_level -= 1

    @property
    def _indent(self):
        return '    ' * self._indent_level

    def write(self, text: str):
        self._io.write(''.join(self._indent+line+"\n" for line in text.splitlines()))

    def separate(self):
        self._io.write("\n")

    def flush(self):
        self._io.flush()


class AizeMessage:
    FATAL = 'fatal error'
    ERROR = 'error'
    WARNING = 'warning'
    MESSAGE = 'message'
    NOTE = 'note'

    LEVELS = [FATAL, ERROR, WARNING, MESSAGE, NOTE]

    def __init__(self, level: str):
        if level not in self.LEVELS:
            raise ValueError(f"level {level!r} is not valid")
        self.level = level

    def display(self, reporter: Reporter):
        raise NotImplementedError()


class ErrorHandler:
    def __init__(self, err_out: IO = None):
        self.err_out = sys.stderr if err_out is None else err_out

        self.messages: List[AizeMessage] = []

        self.is_flushing: bool = False

    def handle_message(self, msg: AizeMessage):
        self.messages.append(msg)
        if msg.level == AizeMessage.FATAL:
            self.flush_errors()

    def flush_errors(self):
        if self.is_flushing:
            return
        self.is_flushing = True

        reporter = Reporter(self.err_out)

        has_errors = False
        for error in self.messages:
            error.display(reporter)
            reporter.separate()
            if error.level in (AizeMessage.ERROR, AizeMessage.FATAL):
                has_errors = True

        reporter.flush()

        if has_errors:
            exit(0)
        self.is_flushing = False
