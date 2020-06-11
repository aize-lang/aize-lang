from __future__ import annotations

import llvmlite.ir as ir
import llvmlite.binding as llvm

from aizec.common import *
from aizec.aize_error import MessageHandler

from aizec.aize_ir import *
from aizec.aize_symbols import *
from aizec.aize_semantics import LiteralData, SymbolData, ResolveTypes

from aizec.aize_backend import Backend, Linker


class LLVMData(Extension):
    class GeneralData:
        def __init__(self, mod: ir.Module):
            self.mod = mod

    def general(self, set_to: GeneralData = None) -> GeneralData:
        return super().general(set_to)

    def program(self, node: ProgramIR, set_to=None):
        raise NotImplementedError()

    def source(self, node: SourceIR, set_to=None):
        raise NotImplementedError()

    def function(self, node: FunctionIR, set_to=None):
        raise NotImplementedError()

    def param(self, node: ParamIR, set_to=None):
        raise NotImplementedError()

    class ExprData:
        def __init__(self, val: ir.Value):
            self.val = val

    def expr(self, node: ExprIR, set_to: ExprData = None) -> ExprData:
        return super().expr(node, set_to)

    class TypeData:
        def __init__(self, llvm_type: ir.Type):
            self.llvm_type = llvm_type

    def type(self, node: TypeIR, set_to: TypeData = None) -> TypeData:
        return super().type(node, set_to)


class GenerateLLVM(IRTreePass):
    def __init__(self, aize_ir: IR):
        super().__init__(aize_ir)

        self.symbols: SymbolData = self.get_ext(SymbolData)
        self.llvm: LLVMData = self.add_ext(LLVMData)

        self.llvm.general(set_to=LLVMData.GeneralData(ir.Module()))

        self.builder = ir.IRBuilder()

    @classmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        return {LiteralData, SymbolData}

    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return {ResolveTypes}

    @classmethod
    def get_llvm(cls, aize_ir: IR) -> ir.Module:
        if LLVMData not in aize_ir.extensions:
            raise ValueError("GenerateLLVM has not been run over the ir yet.")
        return aize_ir.extensions[LLVMData].general().mod

    def was_successful(self) -> bool:
        MessageHandler.flush_messages()
        return True

    @property
    def mod(self) -> ir.Module:
        return self.llvm.general().mod

    def resolve_type(self, type: TypeSymbol) -> ir.Type:
        if isinstance(type, IntTypeSymbol):
            llvm_type = ir.IntType(type.bit_size)
        else:
            raise NotImplementedError(type)
        return llvm_type

    def visit_program(self, program: ProgramIR):
        for source in program.sources:
            self.visit_source(source)

    def visit_source(self, source: SourceIR):
        for top_level in source.top_levels:
            self.visit_top_level(top_level)

    def visit_class(self, cls: ClassIR):
        pass

    def visit_function(self, func: FunctionIR):
        param_types = []
        for param in func.params:
            param_type = param.type
            self.visit_type(param_type)
            param_types.append(self.llvm.type(param_type).llvm_type)
        self.visit_type(func.ret)
        ret_type = self.llvm.type(func.ret).llvm_type
        llvm_func_type = ir.FunctionType(ret_type, param_types)

        llvm_func = ir.Function(self.mod, llvm_func_type, func.name)

        self.builder.position_at_start(llvm_func.append_basic_block("entry"))
        for stmt in func.body:
            self.visit_stmt(stmt)

    def visit_return(self, ret: ReturnIR):
        expr = ret.expr
        self.visit_expr(expr)
        llvm_val = self.llvm.expr(expr).val
        self.builder.ret(llvm_val)

    def visit_int(self, num: IntIR):
        llvm_type = self.resolve_type(self.symbols.expr(num).return_type)
        self.llvm.expr(num, set_to=LLVMData.ExprData(ir.Constant(llvm_type, num.num)))

    def visit_get_type(self, type: GetTypeIR):
        resolved: TypeSymbol = self.symbols.type(type).resolved_type
        llvm_type = self.resolve_type(resolved)
        self.llvm.type(type, set_to=LLVMData.TypeData(llvm_type))


class LLVMBackend(Backend):
    llvm.initialize()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()

    def __init__(self, aize_ir: IR):
        super().__init__(aize_ir)
        self.llvm_ir = self.to_llvm(aize_ir)

    @staticmethod
    def to_llvm(aize_ir: IR) -> ir.Module:
        PassScheduler(aize_ir, [GenerateLLVM]).run_scheduled()
        return GenerateLLVM.get_llvm(aize_ir)

    def run_backend(self):
        target = llvm.Target.from_default_triple()
        machine = target.create_target_machine(codemodel='small')

        llvm_mod = llvm.parse_assembly(str(self.llvm_ir))
        object_data = machine.emit_object(llvm_mod)

        if self.output_path is None:
            self.output_path = Path("a.exe")

        temp_dir = self.output_path.parent
        if (temp_path := temp_dir / 'temp.o').exists():
            i = 0
            while (temp_path := (temp_dir / f"temp_{i}.o")).exists():
                i += 1

        with temp_path.open("wb") as out:
            out.write(object_data)

        try:
            linker = Linker.get_linker("")([temp_path], self.output_path)
            linker.link_files()
        finally:
            temp_path.unlink()

    def run_output(self):
        Linker.process_call(self.output_path)
