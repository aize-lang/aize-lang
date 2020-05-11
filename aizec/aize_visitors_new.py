
from aizec.aize_ast import *


class ASTVisitor:
    def visit_program(self, program: Program):
        raise NotImplementedError()

    def visit_source(self, source: Source):
        raise NotImplementedError()

    def visit_top_level(self, top_level: TopLevel):
        if isinstance(top_level, Class):
            return self.visit_class(top_level)
        elif isinstance(top_level, Function):
            return self.visit_function(top_level)

    def visit_class(self, cls: Class):
        raise NotImplementedError()


class
