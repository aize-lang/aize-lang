from typing import IO


class AizeError(Exception):
    def display(self, file: IO):
        raise NotImplementedError()


class CompilerError(AizeError):
    def __init__(self, msg: str):
        self.msg = msg

    def display(self, file: IO):
        file.write(self.msg + "\n")