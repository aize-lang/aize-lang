from __future__ import annotations

from typing import *

from aizec.aize_ast import *
from aizec.aize_error import AizeMessage, Reporter, MessageHandler
from aizec.aize_pass_data import PositionData
from aizec.aize_symbols import Symbol, VariableSymbol, TypeSymbol, FunctionTypeSymbol, NamespaceSymbol, SymbolError

from aizec.aize_visitors import ProgramVisitor, TopLevelVisitor, StmtVisitor, ExprVisitor, TypeVisitor, ASTPass


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


class TypeCheckingError(AizeMessage):
    def __init__(self, source_name: str, pos: PositionData, msg: str, note: AizeMessage = None):
        super().__init__(self.ERROR)
        self.source = source_name
        self.pos = pos
        self.msg = msg

        self.note = note

    @classmethod
    def from_nodes(cls, definition: Node, offender: Node):
        offender_pos = PositionData.of(offender)
        def_pos = PositionData.of(definition)
        note = DefinitionNote.from_node(definition, "Declared here")
        error = cls(offender_pos.get_source_name(), offender_pos, "Expected type , got type", note)
        return error

    def display(self, reporter: Reporter):
        reporter.positioned_error("Type Checking Error", self.source, self.pos, self.msg)
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


# region Useful Visitors

class TypeResolver(TypeVisitor[TypeSymbol]):
    def visit_get(self, type: GetTypeAnnotation) -> TypeSymbol:
        try:
            return self.table.lookup_type(type.type)
        except SymbolError as err:
            error = DefinitionError.name_undefined(type, err.data)
            MessageHandler.handle_message(error)
            return self.table.error_type

# endregion


class Initialize(ASTPass[None, None, None, None, None]):
    class CustomProgramVisitor(ProgramVisitor[None]):
        @staticmethod
        def create_builtins(program: Program) -> NamespaceSymbol:
            # TODO find a better way to initialize the global namespace
            def define_type(name: str):
                type_symbol = TypeSymbol(name, Node().add_data(PositionData(BuiltinSource(), 1, (0, 4))))
                builtin_namespace.define_type(type_symbol)

            builtin_namespace = NamespaceSymbol("<builtins>", program)

            define_type("int")

            define_type("<errored type>")

            return builtin_namespace

        def visit_program(self, program: Program) -> None:
            builtin_namespace = self.create_builtins(program)
            self.table.define_top(builtin_namespace, is_body=True)

            with self.enter_body(program):
                for source in program.sources:
                    self.visit_source(source)

        def visit_source(self, source: Source) -> None:
            source_body = NamespaceSymbol(f"<{source.get_name()} globals>", source)
            self.table.define_namespace(source_body, visible=False, is_body=True)

    def __init__(self):
        super().__init__(program_visitor=self.CustomProgramVisitor())


class DeclareTypes(ASTPass[None, None, None, None, None]):
    class TopLevelSearcher(TopLevelVisitor[None]):
        def visit_class(self, cls: Class) -> None:
            cls_type = TypeSymbol(cls.name, cls)
            try:
                self.table.define_type(cls_type)
            except SymbolError as err:
                error = DefinitionError.name_existing(cls, err.data)
                MessageHandler.handle_message(error)
                return

        def visit_function(self, func: Function) -> None:
            pass

    def __init__(self):
        super().__init__(top_level_visitor=self.TopLevelSearcher())


class DefineTypes(ASTPass[None, None, None, None, None]):
    class TopLevelSearcher(TopLevelVisitor[None]):
        def visit_class(self, cls: Class) -> None:
            # TODO implement type definition
            pass

        def visit_function(self, func: Function) -> None:
            pass

    def __init__(self):
        super().__init__(top_level_visitor=self.TopLevelSearcher())


class DeclareFunctions(ASTPass[None, None, None, None, TypeSymbol]):
    class TopLevelSearcher(TopLevelVisitor[None]):
        ast_pass: DeclareFunctions

        def visit_class(self, cls: Class) -> None:
            # TODO search through methods for functions (if I add inline functions that are top-levels)
            pass

        def visit_function(self, func: Function) -> None:
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

            func_type = FunctionTypeSymbol(f"<{func.name} type>", func, list(params.values()), ret)
            self.table.define_type(func_type, visible=False)

            func_value = VariableSymbol(func.name, func_type, func)
            try:
                self.table.define_value(func_value)
            except SymbolError as err:
                error = DefinitionError.name_existing(func, err.data)
                MessageHandler.handle_message(error)
                return

    def __init__(self):
        super().__init__(top_level_visitor=self.TopLevelSearcher(), type_visitor=TypeResolver())


class ResolveSymbols(ASTPass[None, None, None, TypeSymbol, TypeSymbol]):
    class TopLevelResolver(TopLevelVisitor[None]):
        def visit_class(self, cls: Class) -> None:
            pass

        def visit_function(self, func: Function) -> None:
            with self.enter_body(func):
                for stmt in func.body:
                    self.ast_pass.visit_stmt(stmt)

    class StmtResolver(StmtVisitor[None]):
        ast_pass: ResolveSymbols

        def visit_var_decl(self, decl: VarDeclStmt) -> None:
            type = self.ast_pass.visit_type(decl.annotation)
            value_type = self.ast_pass.visit_expr(decl.value)
            if not type.is_subtype(value_type):
                error = TypeCheckingError.from_nodes(decl, decl.value)
                MessageHandler.handle_message(error)

        def visit_return(self, ret: ReturnStmt):
            pass

    class ExprResolver(ExprVisitor[TypeSymbol]):
        def visit_int(self, num: IntLiteral) -> TypeSymbol:
            return self.table.get_builtin_type("int")

        def visit_get_var(self, var: GetVarExpr) -> TypeSymbol:
            try:
                return self.table.lookup_value(var.var).type
            except SymbolError as err:
                error = DefinitionError.name_undefined(var, var.var)
                MessageHandler.handle_message(error)
                return self.table.error_type

    def __init__(self):
        super().__init__(top_level_visitor=self.TopLevelResolver(),
                         stmt_visitor=self.StmtResolver(),
                         type_visitor=TypeResolver(),
                         expr_visitor=self.ExprResolver())


class SemanticAnalyzer:
    PASSES: List[Type[ASTPass]] = [
        Initialize,
        DeclareTypes,
        DefineTypes,
        DeclareFunctions,
        ResolveSymbols,
    ]

    def __init__(self):
        pass

    @classmethod
    def analyze(cls, program: Program):
        analyzer = cls()
        for analysis_pass in cls.PASSES:
            analysis_pass.analyze(program)
            MessageHandler.flush_messages()
