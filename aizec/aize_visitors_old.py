from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar, Generic

from aizec.aize_ast import *
from aizec.aize_symbols import BodyData, SymbolTable

T = TypeVar('T')
PR = TypeVar('PR')
TLR = TypeVar('TLR')
SR = TypeVar('SR')
ER = TypeVar('ER')
TR = TypeVar('TR')


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


class ProgramVisitor(NodeVisitor, ABC, Generic[PR]):
    @abstractmethod
    def visit_program(self, program: Program) -> PR:
        pass

    @abstractmethod
    def visit_source(self, source: Source) -> PR:
        pass


class TopLevelVisitor(NodeVisitor, ABC, Generic[TLR]):
    def visit_top_level(self, top_level: TopLevel) -> TLR:
        if isinstance(top_level, Class):
            return self.visit_class(top_level)
        elif isinstance(top_level, Function):
            return self.visit_function(top_level)
        else:
            raise TypeError(f"incorrect type: {top_level.__class__}")

    @abstractmethod
    def visit_class(self, cls: Class) -> TLR:
        pass

    @abstractmethod
    def visit_function(self, func: Function) -> TLR:
        pass


class StmtVisitor(NodeVisitor, ABC, Generic[SR]):
    def visit_stmt(self, stmt: Stmt) -> SR:
        if isinstance(stmt, VarDeclStmt):
            return self.visit_var_decl(stmt)
        elif isinstance(stmt, ReturnStmt):
            return self.visit_return(stmt)
        else:
            raise TypeError(f"incorrect type: {stmt.__class__}")

    @abstractmethod
    def visit_var_decl(self, decl: VarDeclStmt) -> SR:
        pass

    @abstractmethod
    def visit_return(self, ret: ReturnStmt) -> SR:
        pass


class ExprVisitor(NodeVisitor, ABC, Generic[ER]):
    def visit_expr(self, expr: Expr) -> ER:
        if isinstance(expr, IntLiteral):
            return self.visit_int(expr)
        elif isinstance(expr, GetVarExpr):
            return self.visit_get_var(expr)
        else:
            raise TypeError(f"incorrect type: {expr.__class__}")

    @abstractmethod
    def visit_get_var(self, var: GetVarExpr) -> ER:
        pass

    @abstractmethod
    def visit_int(self, num: IntLiteral) -> ER:
        pass


class TypeVisitor(NodeVisitor, ABC, Generic[TR]):
    def visit_type(self, type: TypeAnnotation) -> TR:
        if isinstance(type, GetTypeAnnotation):
            return self.visit_get(type)
        else:
            raise TypeError(f"incorrect type: {type.__class__}")

    def visit_get(self, type: GetTypeAnnotation) -> TR:
        pass

# endregion


# region base visitors
class ProgramTraverser(ProgramVisitor[None]):
    def visit_program(self, program: Program) -> None:
        with self.enter_body(program):
            for source in program.sources:
                self.visit_source(source)

    def visit_source(self, source: Source) -> None:
        with self.enter_body(source):
            for top_level in source.top_levels:
                self.ast_pass.visit_top_level(top_level)


class TopLevelTraverser(TopLevelVisitor[None]):
    def visit_class(self, cls: Class) -> None:
        pass

    def visit_function(self, func: Function) -> None:
        pass


class StmtTraverser(StmtVisitor[None]):
    def visit_var_decl(self, decl: VarDeclStmt) -> None:
        pass

    def visit_return(self, ret: ReturnStmt) -> None:
        pass


class ExprTraverser(ExprVisitor[None]):
    def visit_get_var(self, var: GetVarExpr) -> None:
        pass

    def visit_int(self, num: IntLiteral) -> None:
        pass


class TypeTraverser(TypeVisitor[None]):
    def visit_get(self, type: GetTypeAnnotation) -> None:
        pass

# endregion


class ASTPass(Generic[PR, TLR, SR, ER, TR]):
    def __init__(self,
                 program_visitor: ProgramVisitor[PR] = None,
                 top_level_visitor: TopLevelVisitor[TLR] = None,
                 stmt_visitor: StmtVisitor[SR] = None,
                 expr_visitor: ExprVisitor[ER] = None,
                 type_visitor: TypeVisitor[TR] = None):
        self.program_visitor: ProgramVisitor[PR] = (program_visitor or ProgramTraverser()).with_pass(self)
        self.top_level_visitor: TopLevelVisitor[TLR] = (top_level_visitor or TopLevelTraverser()).with_pass(self)
        self.stmt_visitor: StmtVisitor[SR] = (stmt_visitor or StmtTraverser()).with_pass(self)
        self.expr_visitor: ExprVisitor[ER] = (expr_visitor or ExprTraverser()).with_pass(self)
        self.type_visitor: TypeVisitor[TR] = (type_visitor or TypeTraverser()).with_pass(self)

        self.table = SymbolTable()

    @classmethod
    def analyze(cls, program: Program):
        ast_pass = cls()
        return ast_pass.visit_program(program)

    def visit_program(self, program: Program) -> PR:
        return self.program_visitor.visit_program(program)

    def visit_source(self, source: Source) -> PR:
        return self.program_visitor.visit_source(source)

    def visit_top_level(self, top_level: TopLevel) -> TLR:
        return self.top_level_visitor.visit_top_level(top_level)

    def visit_stmt(self, stmt: Stmt) -> SR:
        return self.stmt_visitor.visit_stmt(stmt)

    def visit_expr(self, expr: Expr) -> ER:
        return self.expr_visitor.visit_expr(expr)

    def visit_type(self, type: TypeAnnotation) -> TR:
        return self.type_visitor.visit_type(type)
