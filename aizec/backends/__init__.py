from aizec.common.error import CompilerError
from aizec.common.interfaces import Backend, Program
from aizec.common import *
from aizec.backends.c import C


class NoBackend(Backend):
    @classmethod
    def generate(cls, ast: Program, out, config, level):
        return cls()

    def delete_temp(self):
        pass

    def run(self):
        pass


def get_backend(language: str) -> Cls[Backend]:
    if language in ('c', 'C'):
        return C
    elif language in ('no', '-'):
        return NoBackend
    else:
        raise CompilerError(f"Language '{language}' not recognized.")

