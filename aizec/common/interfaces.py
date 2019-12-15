from pathlib import Path

from aizec.common.aize_ast import Program
from aizec.common.sematics import SemanticAnalysis


class Frontend:
    @classmethod
    def make_ast(cls, file: Path) -> Program:
        raise NotImplementedError()


class Backend:
    @classmethod
    def generate(cls, ast: Program, out: Path, config, level: str) -> 'Backend':
        raise NotImplementedError()

    def delete_temp(self):
        raise NotImplementedError()

    def run(self):
        raise NotImplementedError()


def analyze_ast(ast: Program):
    SemanticAnalysis(ast).visit(ast)
