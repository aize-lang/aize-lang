from __future__ import annotations

import llvmlite.ir as ir
import llvmlite.binding as llvm

from aizec.common import *
from aizec.aize_error import MessageHandler

from aizec.aize_ir import *
from aizec.aize_symbols import *
from aizec.aize_semantics import LiteralData, SymbolData, DefaultPasses

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

    class FunctionData:
        def __init__(self, llvm_func: ir.Function):
            self.llvm_func = llvm_func

    def function(self, node: FunctionIR, set_to: FunctionData = None) -> FunctionData:
        return super().function(node, set_to)

    def param(self, node: ParamIR, set_to=None):
        raise NotImplementedError()

    class ExprData:
        def __init__(self, val: ir.Value):
            self.val = val

    def expr(self, node: ExprIR, set_to: ExprData = None) -> ExprData:
        return super().expr(node, set_to)

    def get_var(self, node: GetVarIR, set_to=None):
        raise NotImplementedError()

    class TypeData:
        def __init__(self, llvm_type: ir.Type):
            self.llvm_type = llvm_type

    def type(self, node: TypeIR, set_to: TypeData = None) -> TypeData:
        return super().type(node, set_to)

    # region Extension Extensions
    class DeclData:
        def __init__(self, value: ir.Value):
            self.value = value

    def decl(self, node: NodeIR, set_to: DeclData = None) -> DeclData:
        return super().ext(node, 'decl', set_to)
    # endregion


GenerateLLVM = IRPassSequence("GenerateLLVM")
PassesRegister.register(GenerateLLVM)


@PassesRegister.register(to_sequences=[GenerateLLVM])
class InitLLVM(IRTreePass):
    def __init__(self, aize_ir: IR):
        super().__init__(aize_ir)

        self.llvm: LLVMData = self.add_ext(LLVMData)

        self.llvm.general(set_to=LLVMData.GeneralData(ir.Module()))

    @classmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        return set()

    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return set()

    def was_successful(self) -> bool:
        MessageHandler.flush_messages()
        return True


@PassesRegister.register(to_sequences=[GenerateLLVM])
class DeclareFunctions(IRTreePass):
    def __init__(self, aize_ir: IR):
        super().__init__(aize_ir)

        self.symbols: SymbolData = self.get_ext(SymbolData)
        self.literals: LiteralData = self.get_ext(LiteralData)
        self.llvm: LLVMData = self.get_ext(LLVMData)

        self.builder = ir.IRBuilder()

    @property
    def mod(self) -> ir.Module:
        return self.llvm.general().mod

    @classmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        return {LiteralData, SymbolData, LLVMData}

    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return {DefaultPasses, InitLLVM}

    def was_successful(self) -> bool:
        MessageHandler.flush_messages()
        return True

    def visit_program(self, program: ProgramIR):
        for source in program.sources:
            self.visit_source(source)

    def visit_source(self, source: SourceIR):
        for top_level in source.top_levels:
            self.visit_top_level(top_level)

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
        self.llvm.function(func, LLVMData.FunctionData(llvm_func))
        self.llvm.decl(func, LLVMData.DeclData(llvm_func))

        for param, llvm_arg in zip(func.params, llvm_func.args):
            self.llvm.decl(param, LLVMData.DeclData(llvm_arg))

    def resolve_type(self, type: TypeSymbol) -> ir.Type:
        if isinstance(type, IntTypeSymbol):
            llvm_type = ir.IntType(type.bit_size)
        elif isinstance(type, FunctionTypeSymbol):
            llvm_type = ir.FunctionType(self.resolve_type(type.ret), [self.resolve_type(param) for param in type.params])
        else:
            raise NotImplementedError(type)
        return llvm_type

    def visit_get_type(self, type: GetTypeIR):
        resolved: TypeSymbol = self.symbols.type(type).resolved_type
        llvm_type = self.resolve_type(resolved)
        self.llvm.type(type, set_to=LLVMData.TypeData(llvm_type))


@PassesRegister.register(to_sequences=[GenerateLLVM])
class DefineFunctions(IRTreePass):
    def __init__(self, aize_ir: IR):
        super().__init__(aize_ir)

        self.symbols: SymbolData = self.get_ext(SymbolData)
        self.literals: LiteralData = self.get_ext(LiteralData)
        self.llvm: LLVMData = self.get_ext(LLVMData)

        self.builder = ir.IRBuilder()

    @property
    def mod(self) -> ir.Module:
        return self.llvm.general().mod

    @classmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        return {LiteralData, SymbolData, LLVMData}

    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return {DefaultPasses, InitLLVM, DeclareFunctions}

    def was_successful(self) -> bool:
        MessageHandler.flush_messages()
        return True

    def resolve_type(self, type: TypeSymbol) -> ir.Type:
        if isinstance(type, IntTypeSymbol):
            llvm_type = ir.IntType(type.bit_size)
        elif isinstance(type, FunctionTypeSymbol):
            llvm_type = ir.FunctionType(self.resolve_type(type.ret), [self.resolve_type(param) for param in type.params])
        else:
            raise NotImplementedError(type)
        return llvm_type

    def visit_program(self, program: ProgramIR):
        for source in program.sources:
            self.visit_source(source)

    def visit_source(self, source: SourceIR):
        for top_level in source.top_levels:
            self.visit_top_level(top_level)

    def visit_function(self, func: FunctionIR):
        llvm_func = self.llvm.function(func).llvm_func
        self.builder.position_at_start(llvm_func.append_basic_block("entry"))
        for stmt in func.body:
            self.visit_stmt(stmt)

    def visit_return(self, ret: ReturnIR):
        expr = ret.expr
        self.visit_expr(expr)
        llvm_val = self.llvm.expr(expr).val
        self.builder.ret(llvm_val)

    def visit_int(self, num: IntIR):
        # TODO add bit-size symbol data for int so resolve type is not needed
        llvm_type = self.resolve_type(self.symbols.expr(num).return_type)
        self.llvm.expr(num, set_to=LLVMData.ExprData(ir.Constant(llvm_type, num.num)))

    def visit_call(self, call: CallIR):
        self.visit_expr(call.callee)
        callee_val = self.llvm.expr(call.callee).val
        arg_vals = []
        for arg in call.arguments:
            self.visit_expr(arg)
            arg_val = self.llvm.expr(arg).val
            arg_vals.append(arg_val)

        llvm_val = self.builder.call(callee_val, arg_vals)

        self.llvm.expr(call, LLVMData.ExprData(llvm_val))

    def visit_get_var(self, get_var: GetVarIR):
        symbol = self.symbols.get_var(get_var).symbol
        if symbol == self.literals.general().puts:
            llvm_val = ir.Function(self.mod, self.resolve_type(symbol.type), "puts")
        else:
            declarer = symbol.declarer
            llvm_val = self.llvm.decl(declarer).value
        self.llvm.expr(get_var, LLVMData.ExprData(llvm_val))

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
        self.emit_llvm = False

    @staticmethod
    def to_llvm(aize_ir: IR) -> ir.Module:
        PassScheduler(aize_ir, [GenerateLLVM]).run_scheduled()
        llvm_ir = aize_ir.extensions[LLVMData].general().mod
        return llvm_ir

    def handle_option(self, option: str) -> bool:
        if option == 'emit-llvm':
            self.emit_llvm = True
            return True
        else:
            return False

    def run_backend(self):
        if self.output_path is None:
            output_form = Path.cwd() / Path("a")
            output_path = output_form.with_suffix(".exe")
            self.output_path = output_path
        else:
            output_form = self.output_path.absolute().parent
            output_path = self.output_path

        if self.emit_llvm:
            llvm_file = self.output_path.with_suffix(".ll")
            with llvm_file.open("w") as file:
                file.write(str(self.llvm_ir))

        target = llvm.Target.from_default_triple()
        machine = target.create_target_machine(codemodel='small')

        llvm_mod = llvm.parse_assembly(str(self.llvm_ir))
        object_data = machine.emit_object(llvm_mod)

        if (temp_path := output_form.with_suffix(".o")).exists():
            i = 0
            while (temp_path := (output_form + f"_{i}").with_suffix(".o")).exists():
                i += 1

        with temp_path.open("wb") as out:
            out.write(object_data)

        try:
            linker = Linker.get_linker("")([temp_path], output_path)
            linker.link_files()
        finally:
            temp_path.unlink()

    def run_output(self):
        return_code = Linker.process_call([self.output_path])
        print("Returned with code:", return_code)
