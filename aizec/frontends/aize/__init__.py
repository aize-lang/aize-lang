from aizec.common.interfaces import Frontend, analyze_ast, Program
from aizec.common import *
from aizec.frontends.aize.parser import AizeParser
from aizec.frontends.aize.parse_lark import AizeLarkParser


class Aize(Frontend):
    @classmethod
    def make_ast(cls, file: Path) -> Program:
        ast = AizeParser.parse(file)
        analyze_ast(ast)
        return ast


class AizeLark(Frontend):
    @classmethod
    def make_ast(cls, file: Path) -> Program:
        ast = AizeLarkParser.parse(file)
        analyze_ast(ast)
        return ast
