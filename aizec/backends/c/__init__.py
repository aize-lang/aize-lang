from aizec.common.interfaces import Backend
from ...common import *
from .gen import CGenerator


class C(Backend):
    @classmethod
    def generate(cls, ast, args):
        CGenerator.compile(ast, args)