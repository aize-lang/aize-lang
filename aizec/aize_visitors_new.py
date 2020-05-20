
from aizec.aize_ast import *
from aizec.aize_symbols import SymbolTable, BodyData


class ASTVisitor:
    def __init__(self, program: Program):
        self.program = program

    def visit_program(self, program: Program):
        for source in program.sources:
            self.visit_source(source)

    def visit_source(self, source: Source):
        for top_level in source.top_levels:
            self.visit_top_level(top_level)

    def visit_top_level(self, top_level: TopLevel):
        if isinstance(top_level, Class):
            return self.visit_class(top_level)
        elif isinstance(top_level, Function):
            return self.visit_function(top_level)
        else:
            raise TypeError(f"Expected a top-level node, got {top_level}")

    def visit_class(self, cls: Class):
        raise NotImplementedError()

    def visit_function(self, func: Function):
        raise NotImplementedError()


class ASTPass(ASTVisitor):
    def __init__(self, program: Program):
        super().__init__(program)

        self.table = SymbolTable(program)

    def enter_body(self, node: Node):
        return self.table.enter(BodyData.of(node).body_namespace)

    def visit_program(self, program: Program):
        with self.enter_body(program):
            super().visit_program(program)

    def visit_source(self, source: Source):
        with self.enter_body(source):
            super().visit_source(source)