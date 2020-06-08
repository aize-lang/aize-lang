from __future__ import annotations

import llvmlite.ir as ir
import llvmlite.binding as binding

from aizec.aize_symbols import SymbolData, TypeSymbol, FunctionTypeSymbol
from aizec.aize_visitors_old import ProgramVisitor, TopLevelVisitor, StmtVisitor, ExprVisitor, TypeVisitor, ASTPass
from aizec.aize_ast import *


class IRToLLVM(ASTPass):
    class ProgramToLLVM(ProgramVisitor):
        ast_pass: IRToLLVM

        def visit_program(self, program: Program):
            module = ir.Module(program.main_source.get_name())

            for source in program.sources:
                self.visit_source(source)

        def visit_source(self, source: Source):
            for top_level in source.top_levels:
                self.ast_pass.visit_top_level(top_level)

    class TopLevelsToLLVM(TopLevelVisitor):
        ast_pass: IRToLLVM

        def visit_class(self, cls: Class):
            # Todo
            pass

        def visit_function(self, func: Function):
            func_type = SymbolData.of(func).get_value().type
            llvm_func_type = self.ast_pass.visit_type(func_type)
            llvm_func = ir.Function(self.ast_pass.module, llvm_func_type, func.name)

            self.ast_pass.builder.position_at_start(llvm_func.append_basic_block("entry"))

            for stmt in func.body:
                self.ast_pass.visit_stmt(stmt)

    class StmtsToLLVM(StmtVisitor):
        ast_pass: IRToLLVM

        def visit_var_decl(self, decl: VarDeclStmt):
            type = SymbolData.of(decl).get_value().type
            var = self.ast_pass.builder.alloca(self.ast_pass.visit_type(type))

        def visit_return(self, ret: ReturnStmt):
            self.ast_pass.builder.ret(self.ast_pass.visit_expr(ret.symbol))

    class AizeTypesToLLVM:
        ast_pass: IRToLLVM

        def visit_type(self, type: TypeSymbol) -> ir.Type:
            if isinstance(type, FunctionTypeSymbol):
                return self.visit_func_type(type)
            else:
                raise ValueError(type)

        def visit_func_type(self, ftype: FunctionTypeSymbol) -> ir.FunctionType:
            params = [self.visit_type(param) for param in ftype.params]
            ret = self.visit_type(ftype.ret)
            return ir.FunctionType(ret, params)

    def visit_type(self, type: TypeSymbol) -> ir.Type:
        return self.aize_types_to_llvm.visit_type(type)

    def __init__(self):
        super().__init__(program_visitor=self.ProgramToLLVM(),
                         top_level_visitor=self.TopLevelsToLLVM(),
                         stmt_visitor=self.StmtsToLLVM())

        self.aize_types_to_llvm = self.AizeTypesToLLVM()
        self.aize_types_to_llvm.ast_pass = self

        # noinspection PyTypeChecker
        self.module: ir.Module = None
        # noinspection PyTypeChecker
        self.builder: ir.IRBuilder = ir.IRBuilder()

