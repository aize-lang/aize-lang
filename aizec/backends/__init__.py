from aizec.common.error import CompilerError
from aizec.common.interfaces import Backend, Program
from aizec.common import *
from aizec.backends.c import C


class NoBackend(Backend):
    @classmethod
    def generate(cls, ast: Program, args):
        pass


def get_backend(language: str) -> Cls[Backend]:
    if language in ('c', 'C'):
        return C
    elif language in ('no', '-'):
        return NoBackend
    else:
        raise CompilerError(f"Language '{language}' not recognized.")


def apply_backend(language: str, program: Program, args):
    backend = get_backend(language)
    backend.generate(program, args)

