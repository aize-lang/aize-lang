from __future__ import annotations

from aizec.common import *

from aizec.aize_ast import *


class ASTVisitor(ABC):
    def __init__(self, program: ProgramAST):
        self.program = program

    @abstractmethod
    def handle_malformed_type(self, type: ExprAST):
        pass

    @abstractmethod
    def visit_program(self, program: ProgramAST):
        pass

    @abstractmethod
    def visit_source(self, source: SourceAST):
        pass

    def visit_top_level(self, top_level: TopLevelAST):
        if isinstance(top_level, ClassAST):
            return self.visit_class(top_level)
        elif isinstance(top_level, FunctionAST):
            return self.visit_function(top_level)
        else:
            raise TypeError(f"Expected a top-level node, got {top_level}")

    @abstractmethod
    def visit_class(self, cls: ClassAST):
        pass

    @abstractmethod
    def visit_function(self, func: FunctionAST):
        pass

    @abstractmethod
    def visit_attr(self, attr: AttrAST):
        pass

    def visit_method(self, method: MethodAST):
        if isinstance(method, MethodImplAST):
            return self.visit_method_impl(method)
        elif isinstance(method, MethodSigAST):
            return self.visit_method_sig(method)
        else:
            raise TypeError(f"Expected a method node, got {method}")

    @abstractmethod
    def visit_method_impl(self, method: MethodImplAST):
        pass

    @abstractmethod
    def visit_method_sig(self, method: MethodSigAST):
        pass

    @abstractmethod
    def visit_param(self, param: ParamAST):
        pass

    def visit_stmt(self, stmt: StmtAST):
        if isinstance(stmt, ReturnStmtAST):
            return self.visit_return(stmt)
        else:
            raise TypeError(f"Expected a stmt node, got {stmt}")

    @abstractmethod
    def visit_return(self, ret: ReturnStmtAST):
        pass

    def visit_expr(self, expr: ExprAST):
        if isinstance(expr, IntLiteralAST):
            return self.visit_int(expr)
        else:
            raise TypeError(f"Expected a expr node, got {expr}")

    @abstractmethod
    def visit_int(self, num: IntLiteralAST):
        pass

    @abstractmethod
    def visit_ann(self, ann: ExprAST):
        pass

    def visit_type(self, type: ExprAST):
        if isinstance(type, GetVarExprAST):
            return self.visit_get_type(type)
        else:
            return self.handle_malformed_type(type)

    @abstractmethod
    def visit_get_type(self, type: GetVarExprAST):
        pass
