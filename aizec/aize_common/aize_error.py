from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import IntEnum

from aizec.aize_common.common import *
from aizec.aize_common.aize_source import Source, Position, TextPosition


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
            self.write(f"At {source_name}:")
            self.write(f"{type}: {msg}.")

    def source_error(self, type: str, msg: str, source: Source):
        self.write(f"For {source.get_name()}:")
        self.write(f"{type}: {msg}.")

    def general_error(self, type: str, msg: str):
        self.write(f"{type}: {msg}.")

    @contextmanager
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


class ErrorLevel(IntEnum):
    ALL = 0
    NOTE = 1
    MESSAGE = 2
    WARNING = 3
    ERROR = 4
    FATAL = 5
    NEVER = 6


class AizeMessage(ABC):
    def __init__(self, level: ErrorLevel):
        if not ErrorLevel.ALL < level < ErrorLevel.NEVER:
            raise ValueError(level)
        self.level = level

    def display(self, reporter: Reporter):
        raise NotImplementedError()


class ThrownMessage(Exception):
    def __init__(self, message: AizeMessage):
        self.message = message


class FailFlag(Exception):
    def __init__(self, fail_msgs: List[AizeMessage]):
        self.fail_msgs = fail_msgs


@dataclass(frozen=True)
class ErrorHandlerConfig:
    err_out: IO
    throw_ge: ErrorLevel
    fail_ge: ErrorLevel
    immediate_flush_ge: ErrorLevel


DefaultConfig = ErrorHandlerConfig(
    err_out=sys.stderr,
    throw_ge=ErrorLevel.NEVER,
    fail_ge=ErrorLevel.ERROR,
    immediate_flush_ge=ErrorLevel.FATAL
)


# TODO Fold the class into _ErrorHandler
class MessageHandler:
    _instance: MessageHandler = None
    _config: ErrorHandlerConfig = DefaultConfig

    def __init__(self):
        self.messages: List[AizeMessage] = []

        # For when MessageHandler.flush_messages() is called in a finally block, so only 1 flush_messages is called at a time
        self.is_flushing: bool = False

    def _handle_message(self, msg: AizeMessage):
        if msg.level >= self._config.throw_ge:
            raise ThrownMessage(msg)
        else:
            self.messages.append(msg)
            if msg.level >= self._config.immediate_flush_ge:
                self._flush_messages()

    def _flush_messages(self):
        if self.is_flushing:
            return
        self.is_flushing = True

        reporter = Reporter(self._config.err_out)

        fail = False
        fail_causes = []
        for n, error in enumerate(self.messages):
            error.display(reporter)
            if (n+1) < len(self.messages):
                reporter.separate()
            if error.level >= self._config.fail_ge:
                fail_causes.append(error)
                fail = True

        reporter.flush()

        self.is_flushing = False
        if fail:
            raise FailFlag(fail_causes)

    @classmethod
    def instance(cls):
        if cls._config is None:
            raise ValueError("Set config before using class utilities")
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_config(cls):
        cls._config = DefaultConfig

    @classmethod
    def reset_errors(cls):
        cls.instance().messages = []
        cls.instance().is_flushing = False

    @classmethod
    def set_config(cls, err_out: IO = None, throw_ge: ErrorLevel = None, fail_ge: ErrorLevel = None, immediate_flush_ge: ErrorLevel = None):
        new_err_out = cls._config.err_out if err_out is None else err_out
        new_throw_ge = cls._config.throw_ge if throw_ge is None else throw_ge
        new_fail_ge = cls._config.fail_ge if fail_ge is None else fail_ge
        new_flush_ge = cls._config.immediate_flush_ge if immediate_flush_ge is None else immediate_flush_ge
        cls._config = ErrorHandlerConfig(new_err_out, new_throw_ge, new_fail_ge, new_flush_ge)

    @classmethod
    def handle_message(cls, msg: AizeMessage):
        cls.instance()._handle_message(msg)

    @classmethod
    def flush_messages(cls):
        cls.instance()._flush_messages()

    @classmethod
    def get_config(cls):
        return cls._config
