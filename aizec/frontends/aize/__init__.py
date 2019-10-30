from aizec.common.interfaces import Frontend, analyze_ast, Program
from aizec.common import *
from aizec.frontends.aize.parser import AizeParser


class Aize(Frontend):
    @classmethod
    def make_ast(cls, file: Path) -> Program:
        ast = AizeParser.parse(file)
        analyze_ast(ast)
        return ast
