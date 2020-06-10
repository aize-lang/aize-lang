from __future__ import annotations

import llvmlite.ir as ir
import llvmlite.binding as llvm

from aizec.common import *

from aizec.aize_ir import *
from aizec.aize_semantics import LiteralData, ResolveTypes

from aizec.aize_error import AizeMessage, Reporter, MessageHandler, ErrorLevel
from aizec.aize_source import *
from aizec.aize_symbols import *


class LLVMData(Extension):
    def general(self, set_to = None):
        raise NotImplementedError()


class GenerateLLVM(IRTreePass):
    def __init__(self, aize_ir: IR):
        super().__init__(aize_ir)

        self.mod: ir.Module = ir.Module()

    @classmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        return {LiteralData}

    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return {ResolveTypes}

    def visit_program(self, program: ProgramIR):
        for source in program.sources:
            self.visit_source(source)

    def visit_source(self, source: SourceIR):
        for top_level in source.top_levels:
            self.visit_top_level(top_level)

    def visit_class(self, cls: ClassIR):
        pass

    def visit_function(self, func: FunctionIR):
        pass
        # func_type = func.type_ir()
        # self.visit_type(func_type)
        # llvm_func_type = self.data[GenAnns.func_type, func_type]
        #
        # llvm_func = ir.Function(self.mod, llvm_func_type, func.name)
        #
        # self.data[GenAnns.func, func] = llvm_func
