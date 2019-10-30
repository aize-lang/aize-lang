from aizec.common.error import CompilerError
from aizec.common.interfaces import Frontend
from aizec.common import *
from aizec.frontends.aize import Aize


def get_frontend(language: str) -> Cls[Frontend]:
    if language in ('aize', 'Aize', 'a', 'A'):
        return Aize
    else:
        raise CompilerError(f"Language {language} not recognized")


def apply_frontend(language: str, path: Path, args):
    frontend = get_frontend(language)
    return frontend.make_ast(path)

