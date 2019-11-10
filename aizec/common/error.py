import sys

from aizec.common import *


ERROR_FILE: IO
DEBUG: bool


def init_errors(error_file: IO = sys.stderr, debug: bool = False):
    global ERROR_FILE, DEBUG
    ERROR_FILE = error_file
    DEBUG = debug


class AizeError(Exception):
    def display(self, file: IO):
        raise NotImplementedError()

    @classmethod
    def message(cls, msg: str):
        ERROR_FILE.write(msg + "\n")


class CompilerError(AizeError):
    def __init__(self, msg: str):
        self.msg = msg

    def display(self, file: IO):
        file.write(self.msg + "\n")


def hook_aize_error(exc_type: Cls[T], exc_val: T, exc_tb):
    if isinstance(exc_val, AizeError) and not DEBUG:
        exc_val.display(ERROR_FILE)
    else:
        sys.__excepthook__(exc_type, exc_val, exc_tb)


sys.excepthook = hook_aize_error
