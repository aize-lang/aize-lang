import sys
import contextlib
from typing import List, IO, Union, Literal

from aizec.aize_source import Source, Position, TextPosition


__all__ = ['Reporter', 'AizeMessage',
           'MessageHandler',
           'ThrownMessage']


class Reporter:
    def __init__(self, io: IO):
        self._io = io

        self._indent_level = 0

    def positioned_error(self, type: str, msg: str, pos: Position):
        source_name = pos.get_source_name()
        if isinstance(pos, TextPosition):
            in_context = pos.in_context()
            self.write(f"In {source_name}:")
            self.write(f"{type}: {msg}:")
            self.write(f"{in_context}")
        else:
            self.write(f"In {source_name}:")
            self.write(f"{type}: {msg}.")

    def source_error(self, type: str, msg: str, source: Source):
        self.write(f"For {source.get_name()}:")
        self.write(f"{type}: {msg}.")

    def general_error(self, type: str, msg: str):
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


class ThrownMessage(Exception):
    def __init__(self, message: AizeMessage):
        self.message = message


class _ErrorHandler:
    _instance_ = None

    def __init__(self):
        self.err_out: IO = sys.stderr
        self.throw_messages: bool = False

        self.messages: List[AizeMessage] = []

        self.is_flushing: bool = False

    def handle_message(self, msg: AizeMessage):
        if self.throw_messages:
            raise ThrownMessage(msg)
        else:
            self.messages.append(msg)
            if msg.level == AizeMessage.FATAL:
                self.flush_messages()

    def flush_messages(self):
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

        self.is_flushing = False
        if has_errors:
            exit(0)

    @classmethod
    def get_instance(cls):
        if cls._instance_ is None:
            cls._instance_ = cls()
        return cls._instance_


# TODO Fold the class into _ErrorHandler
class MessageHandler:
    @staticmethod
    def reset_errors():
        _ErrorHandler._instance_ = None

    @staticmethod
    def set_io(io: Union[IO, Literal['stderr']]):
        if isinstance(io, str):
            if io == 'stderr':
                io = sys.stderr
            else:
                raise ValueError(f"Unknown io: {io!r}")
        _ErrorHandler.get_instance().err_out = io

    @staticmethod
    def set_throw(throw: bool):
        _ErrorHandler.get_instance().throw_messages = throw

    @staticmethod
    def handle_message(msg: AizeMessage):
        _ErrorHandler.get_instance().handle_message(msg)

    @staticmethod
    def flush_messages():
        _ErrorHandler.get_instance().flush_messages()
