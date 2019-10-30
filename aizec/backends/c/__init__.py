from aizec.common.interfaces import Backend
from aizec.backends.c.gen import CGenerator


class C(Backend):
    @classmethod
    def generate(cls, ast, args):
        CGenerator.compile(ast, args)
