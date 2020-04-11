from __future__ import annotations

from abc import ABC
from typing import *

from aizec.aize_ast import *
from aizec.aize_error import AizeMessage, Reporter, MessageHandler
from aizec.aize_pass_data import PositionData
from aizec.aize_symbols import Symbol, VariableSymbol, TypeSymbol, NamespaceSymbol, SymbolTable, SymbolError, BodyData

T = TypeVar('T')


# region Errors
class DefinitionError(AizeMessage):
    def __init__(self, source_name: str, pos: PositionData, msg: str, note: AizeMessage = None):
        super().__init__(self.ERROR)
        self.source = source_name
        self.pos = pos
        self.msg = msg

        self.note = note

    @classmethod
    def name_existing(cls, node: Node, existing: Symbol):
        note = DefinitionNote.from_node(existing.node, "Previously defined here")
        error = cls.from_node(node, f"Name '{existing.name}' already defined", note)
        return error

    @classmethod
    def name_undefined(cls, node: Node, name: str):
        error = cls.from_node(node, f"Name '{name}' could not be found")
        return error

    @classmethod
    def param_repeated(cls, func: Node, param: Node, name: str):
        note = DefinitionNote.from_node(param, "Repeated here")
        error = cls.from_node(func, f"Parameter name '{name}' repeated", note)
        return error

    @classmethod
    def from_node(cls, node: Node, msg: str, note: AizeMessage = None):
        pos = PositionData.of(node)
        return cls(pos.get_source_name(), pos, msg, note)

    def display(self, reporter: Reporter):
        reporter.positioned_error("Name Resolution Error", self.source, self.pos, self.msg)
        if self.note is not None:
            reporter.separate()
            with reporter.indent():
                self.note.display(reporter)


class DefinitionNote(AizeMessage):
    def __init__(self, source_name: str, pos: PositionData, msg: str):
        super().__init__(self.NOTE)

        self.source = source_name
        self.pos = pos
        self.msg = msg

    @classmethod
    def from_node(cls, node: Node, msg: str):
        pos = PositionData.of(node)
        return cls(pos.get_source_name(), pos, msg)

    def display(self, reporter: Reporter):
        reporter.positioned_error("Note", self.source, self.pos, self.msg)
# endregion


# region Node Visitor Classes
class NodeVisitor(ABC):
    def __init__(self):
        # noinspection PyTypeChecker
        self.ast_pass: ASTPass = None

    @property
    def table(self):
        return self.ast_pass.table

    def enter_body(self, node: Node):
        return self.table.enter(BodyData.of(node).body_namespace)

    def with_pass(self: T, ast_pass: ASTPass) -> T:
        self.ast_pass = ast_pass
        return self


class ProgramVisitor(NodeVisitor):
    def visit_program(self, program: Program):
        with self.enter_body(program):
            for source in program.sources:
                self.visit_source(source)

    def visit_source(self, source: Source):
        with self.enter_body(source):
            for top_level in source.top_levels:
                self.ast_pass.visit_top_level(top_level)


class TopLevelVisitor(NodeVisitor):
    def visit_top_level(self, top_level: TopLevel):
        if isinstance(top_level, Class):
            return self.visit_class(top_level)
        elif isinstance(top_level, Function):
            return self.visit_function(top_level)
        else:
            raise TypeError(f"incorrect type: {top_level.__class__}")

    def visit_class(self, cls: Class):
        pass

    def visit_function(self, func: Function):
        pass


class TypeVisitor(NodeVisitor):
    def visit_type(self, type: TypeAnnotation):
        if isinstance(type, GetTypeAnnotation):
            return self.visit_get(type)
        else:
            raise TypeError(f"incorrect type: {type.__class__}")

    def visit_get(self, type: GetTypeAnnotation):
        pass

# endregion


class ASTPass:
    def __init__(self,
                 program_visitor: ProgramVisitor = None,
                 top_level_visitor: TopLevelVisitor = None,
                 type_visitor: TypeVisitor = None):
        if program_visitor is None:
            program_visitor = ProgramVisitor()
        if top_level_visitor is None:
            top_level_visitor = TopLevelVisitor()
        if type_visitor is None:
            type_visitor = TypeVisitor()
        self.program_visitor: ProgramVisitor = program_visitor.with_pass(self)
        self.top_level_visitor: TopLevelVisitor = top_level_visitor.with_pass(self)
        self.type_visitor: TypeVisitor = type_visitor.with_pass(self)

        self.table = SymbolTable()

    @classmethod
    def analyze(cls, program: Program):
        ast_pass = cls()
        return ast_pass.visit_program(program)

    def visit_program(self, program: Program):
        return self.program_visitor.visit_program(program)

    def visit_source(self, source: Source):
        return self.program_visitor.visit_source(source)

    def visit_top_level(self, top_level: TopLevel):
        return self.top_level_visitor.visit_top_level(top_level)

    def visit_type(self, type: TypeAnnotation):
        return self.type_visitor.visit_type(type)


class Initialize(ASTPass):
    class CustomProgramVisitor(ProgramVisitor):
        @staticmethod
        def create_builtins(program: Program) -> NamespaceSymbol:
            # TODO find a better way to initialize the global namespace
            def define_type(name: str):
                type_symbol = TypeSymbol(name, Node().add_data(PositionData(BuiltinSource(), 1, (0, 4))))
                builtin_namespace.define_type(type_symbol)

            builtin_namespace = NamespaceSymbol("<builtins>", program)

            define_type("int")

            return builtin_namespace

        def visit_program(self, program: Program):
            builtin_namespace = self.create_builtins(program)
            self.table.define_top(builtin_namespace, is_body=True)

            with self.enter_body(program):
                for source in program.sources:
                    self.visit_source(source)

        def visit_source(self, source: Source):
            source_body = NamespaceSymbol(f"<{source.get_name()} globals>", source)
            self.table.define_namespace(source_body, visible=False, is_body=True)

    def __init__(self):
        super().__init__(program_visitor=self.CustomProgramVisitor())


class DeclareTypes(ASTPass):
    class TopLevelSearcher(TopLevelVisitor):
        def visit_class(self, cls: Class):
            cls_type = TypeSymbol(cls.name, cls)
            try:
                self.table.define_type(cls_type)
            except SymbolError as err:
                error = DefinitionError.name_existing(cls, err.data)
                MessageHandler.handle_message(error)
                return

        def visit_function(self, func: Function):
            pass

    def __init__(self):
        super().__init__(top_level_visitor=self.TopLevelSearcher())


class DefineTypes(ASTPass):
    class TopLevelSearcher(TopLevelVisitor):
        def visit_class(self, cls: Class):
            # TODO implement type definition
            pass

        def visit_function(self, func: Function):
            pass

    def __init__(self):
        super().__init__(top_level_visitor=self.TopLevelSearcher())


class DeclareFunctions(ASTPass):
    class TopLevelSearcher(TopLevelVisitor):
        ast_pass: DeclareFunctions

        def visit_class(self, cls: Class):
            super().visit_class(cls)

        def visit_function(self, func: Function):
            body = NamespaceSymbol(f"<{func.name} body>", func)
            self.table.define_namespace(body, visible=False, is_body=True)

            params: Dict[str, TypeSymbol] = {}
            with self.enter_body(func):
                for param_node in func.params:
                    name, type = param_node.name, self.ast_pass.visit_type(param_node.annotation)
                    params[name] = type
                    param_value = VariableSymbol(name, type, param_node)
                    try:
                        self.table.define_value(param_value)
                    except SymbolError as err:
                        error = DefinitionError.param_repeated(func, param_node, param_node.name)
                        MessageHandler.handle_message(error)
                        continue

            ret = self.ast_pass.visit_type(func.ret)

            func_type = TypeSymbol(f"<{func.name} type>", func)
            self.table.define_type(func_type, visible=False)

            func_value = VariableSymbol(func.name, func_type, func)
            try:
                self.table.define_value(func_value)
            except SymbolError as err:
                error = DefinitionError.name_existing(func, err.data)
                MessageHandler.handle_message(error)
                return

    class TypeResolver(TypeVisitor):
        def visit_get(self, type: GetTypeAnnotation):
            try:
                return self.table.lookup_type(type.type)
            except SymbolError as err:
                error = DefinitionError.name_undefined(type, err.data)
                MessageHandler.handle_message(error)
                return

    def __init__(self):
        super().__init__(top_level_visitor=self.TopLevelSearcher(), type_visitor=self.TypeResolver())

    def visit_type(self, type: TypeAnnotation) -> TypeSymbol:
        return cast(TypeSymbol, super().visit_type(type))

# TODO write a symbol resolution pass
# class ResolveSymbols(ASTAnalysisPass):
#     def visit_Function(self, func: Function):
#         body_namespace = SymbolData.of(func).namespace_symbol
#
#         super().visit_Function(func)


class SemanticAnalyzer:
    PASSES: List[Type[ASTPass]] = [
        Initialize,
        DeclareTypes,
        DefineTypes,
        DeclareFunctions,
    ]

    def __init__(self):
        pass

    @classmethod
    def analyze(cls, program: Program):
        analyzer = cls()
        for analysis_pass in cls.PASSES:
            analysis_pass.analyze(program)
            MessageHandler.flush_messages()
