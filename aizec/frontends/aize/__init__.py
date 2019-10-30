from aizec.common.interfaces import Frontend, analyze_ast, Program
from ...common import *
from .parser import AizeParser


class Aize(Frontend):
    @classmethod
    def make_ast(cls, file: Path) -> Program:
        ast = AizeParser.parse(file)
        analyze_ast(ast)
        return ast
