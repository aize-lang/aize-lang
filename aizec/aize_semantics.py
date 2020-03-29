from __future__ import annotations

from typing import *

from aizec.aize_ast import *
from aizec.aize_error import ErrorHandler
from aizec.aize_symbols import Symbol, VariableSymbol, TypeSymbol, NamespaceSymbol, SymbolTable, SymbolData


class AnalysisPass:
    DEBUG = False

    def __init__(self, error_handler: ErrorHandler):
        self.error_handler = error_handler

    @classmethod
    def analyze(cls, program: Program, error_handler: ErrorHandler):
        analyzer = cls(error_handler)
        analyzer.apply(program)

    def apply(self, program: Program):
        raise NotImplementedError()


class CreateNamespaces(AnalysisPass, ASTVisitor):
    def __init__(self, error_handler: ErrorHandler):
        super().__init__(error_handler)

        self.table: SymbolTable = SymbolTable()

    def enter(self, node: Node):
        return self.table.enter(SymbolData.of(node).namespace_symbol)

    def apply(self, program: Program):
        self.visit(program)

    def visit_Program(self, program: Program):
        builtin_namespace = NamespaceSymbol("<builtins>", {}, program)  # TODO add stuff to builtins
        program.add_data(SymbolData(namespace=builtin_namespace))

        with self.enter(program):
            for source in program.sources:
                self.visit(source)

    def visit_Source(self, source: Source):
        namespace = NamespaceSymbol(f"<{source.get_name()} globals>", {}, source)
        self.table.define_node(source, f"<{source.get_name()} globals>", namespace=namespace)

    def visit_Class(self, cls: Class):
        pass

    def visit_Trait(self, trait: Trait):
        pass

    def visit_Function(self, func: Function):
        pass


class FindTypes(AnalysisPass, ASTVisitor):
    def __init__(self, error_handler: ErrorHandler):
        super().__init__(error_handler)

        self.table: SymbolTable = SymbolTable()

    def enter(self, node: Node):
        return self.table.enter(SymbolData.of(node).namespace_symbol)

    def apply(self, program: Program):
        self.visit(program)

    def visit_Program(self, program: Program):
        with self.enter(program):
            for source in program.sources:
                self.visit(source)

    def visit_Source(self, source: Source):
        with self.enter(source):
            for top_level in source.top_levels:
                self.visit(top_level)

    def visit_Class(self, cls: Class):
        cls_type = TypeSymbol(cls.name, cls)
        self.table.define_node(cls, cls.name, type=cls_type)

    def visit_Trait(self, trait: Trait):
        pass

    def visit_Function(self, func: Function):
        pass


class SemanticAnalyzer:
    PASSES: List[Type[AnalysisPass]] = [
        CreateNamespaces,
        FindTypes,
    ]

    def __init__(self, error_handler: ErrorHandler):
        self.error_handler = error_handler

    @classmethod
    def analyze(cls, program: Program, error_handler: ErrorHandler):
        analyzer = cls(error_handler)
        for analysis_pass in cls.PASSES:
            analysis_pass.analyze(program, error_handler)
