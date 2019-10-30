from aizec.common.error import CompilerError
from aizec.common.interfaces import Backend, Program
from ..common import *
from .c import C


def get_backend(language: str) -> Cls[Backend]:
    if language in ('c', 'C'):
        return C
    else:
        raise CompilerError(f"Language {language} not recognized")


def apply_backend(language: str, program: Program, args):
    backend = get_backend(language)
    backend.generate(program, args)

