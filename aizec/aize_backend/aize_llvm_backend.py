from __future__ import annotations

import llvmlite.ir as ir
import llvmlite.binding as llvm

from aizec.common import *
from aizec.aize_common import MessageHandler

from aizec.ir import IR, Extension
from aizec.ir.nodes import *

from aizec.analysis import SymbolData, \
    TypeSymbol, IntTypeSymbol, FunctionTypeSymbol, StructTypeSymbol, \
    DefaultPasses, MangleNames
from aizec.ir_pass import IRTreePass, IRPassSequence, PassesRegister, PassAlias, PassScheduler

from .aize_backend import CBackend, CLinker


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
        def __init__(self, llvm_func: ir.Function, code_entry: ir.Block):
            self.llvm_func = llvm_func
            self.code_entry = code_entry

    def function(self, node: FunctionIR, set_to: FunctionData = None) -> FunctionData:
        return super().function(node, set_to)

    def param(self, node: ParamIR, set_to=None):
        raise NotImplementedError()

    def stmt(self, node: StmtIR, set_to=None):
        raise NotImplementedError()

    class ExprData:
        def __init__(self, l_val: Optional[ir.Value], r_val: ir.Value):
            self.l_val = l_val
            self.r_val = r_val

    def expr(self, node: ExprIR, set_to: ExprData = None) -> ExprData:
        return super().expr(node, set_to)

    def compare(self, node: CompareIR, set_to=None):
        raise NotImplementedError()

    def arithmetic(self, node: ArithmeticIR, set_to=None):
        raise NotImplementedError()

    def get_var(self, node: GetVarIR, set_to=None):
        raise NotImplementedError()

    def set_var(self, node: SetVarIR, set_to=None):
        raise NotImplementedError()

    def get_attr(self, node: GetAttrIR, set_to=None):
        raise NotImplementedError()

    def set_attr(self, node: SetAttrIR, set_to=None):
        raise NotImplementedError()

    def intrinsic(self, node: IntrinsicIR, set_to=None):
        raise NotImplementedError()

    def get_static_attr_expr(self, node: GetStaticAttrExprIR, set_to=None):
        raise NotImplementedError()

    class TypeData:
        def __init__(self, llvm_type: ir.Type):
            self.llvm_type = llvm_type

    def type(self, node: TypeIR, set_to: TypeData = None) -> TypeData:
        return super().type(node, set_to)

    def namespace(self, node: NamespaceIR, set_to=None):
        raise NotImplementedError()

    # region Extension Extensions
    class DeclData:
        def __init__(self, var: ir.Value, is_ptr: bool):
            self.var_value = var
            self.is_ptr = is_ptr

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


class IRLLVMPass(IRTreePass, ABC):
    def __init__(self, aize_ir: IR):
        super().__init__(aize_ir)

        self.symbols: SymbolData = self.get_ext(SymbolData)
        self.llvm: LLVMData = self.get_ext(LLVMData)

        self.builder = ir.IRBuilder()

    @property
    def mod(self) -> ir.Module:
        return self.llvm.general().mod

    def was_successful(self) -> bool:
        MessageHandler.flush_messages()
        return True

    def resolve_type(self, type: TypeSymbol) -> ir.Type:
        if isinstance(type, IntTypeSymbol):
            llvm_type = ir.IntType(type.bit_size)
        elif isinstance(type, FunctionTypeSymbol):
            llvm_type = ir.FunctionType(self.resolve_type(type.ret), [self.resolve_type(param) for param in type.params])
        elif isinstance(type, StructTypeSymbol):
            llvm_type = ir.LiteralStructType([self.resolve_type(field_type) for field_name, field_type in type.fields.items()])
        else:
            raise NotImplementedError(type)
        return llvm_type

    def visit_program(self, program: ProgramIR):
        for source in program.sources:
            self.visit_source(source)

    def visit_source(self, source: SourceIR):
        for top_level in source.top_levels:
            self.visit_top_level(top_level)


@PassesRegister.register(to_sequences=[GenerateLLVM])
class DeclareFunctions(IRLLVMPass):
    def __init__(self, aize_ir: IR):
        super().__init__(aize_ir)

        self._main_builder = ir.IRBuilder()
        self._last_ret = ir.Constant(ir.IntType(32), 0)

    @classmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        return {SymbolData, LLVMData}

    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return {DefaultPasses, InitLLVM, MangleNames}

    def call_func_in_main(self, func: ir.Function):
        ret = self._main_builder.call(func, [])
        self._last_ret = ret

    def visit_program(self, program: ProgramIR):
        main_func = ir.Function(self.mod, ir.FunctionType(ir.IntType(32), []), "main")
        main_entry = main_func.append_basic_block("entry")
        self._main_builder.position_at_start(main_entry)

        for source in program.sources:
            self.visit_source(source)

        self._main_builder.ret(self._last_ret)

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
        self.llvm.decl(func, LLVMData.DeclData(llvm_func, is_ptr=False))

        if 'link_in' in self.symbols.function(func).attrs:
            entry = None
        else:
            prep = llvm_func.append_basic_block("prep")
            self.builder.position_at_start(prep)

            for param, llvm_arg in zip(func.params, llvm_func.args):
                param_ptr = self.builder.alloca(llvm_arg.type)
                self.builder.store(llvm_arg, param_ptr)
                self.llvm.decl(param, LLVMData.DeclData(param_ptr, is_ptr=True))

            entry = self.builder.append_basic_block("entry")
            self.builder.branch(entry)

        func_attrs = self.symbols.function(func).attrs
        if 'entry' in func_attrs:
            # TODO Make an analysis pass for all of these and just put it in the function extension
            # TODO Do the above so I can check if I recognized all attributes
            self.call_func_in_main(llvm_func)

        self.llvm.function(func, LLVMData.FunctionData(llvm_func, entry))

    def visit_get_type(self, type: GetTypeIR):
        resolved: TypeSymbol = self.symbols.type(type).resolved_type
        llvm_type = self.resolve_type(resolved)
        self.llvm.type(type, set_to=LLVMData.TypeData(llvm_type))


@PassesRegister.register(to_sequences=[GenerateLLVM])
class DefineFunctions(IRLLVMPass):
    @classmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        return {SymbolData, LLVMData}

    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return {DefaultPasses, InitLLVM, DeclareFunctions, MangleNames}

    def visit_function(self, func: FunctionIR):
        llvm_func = self.llvm.function(func).llvm_func
        code_entry = self.llvm.function(func).code_entry
        if 'link_in' in self.symbols.function(func).attrs:
            pass
        else:
            self.builder.position_at_end(code_entry)
            for stmt in func.body:
                self.visit_stmt(stmt)
            if not self.builder.block.is_terminated:
                self.builder.unreachable()

    def visit_if(self, if_: IfStmtIR):
        self.visit_expr(if_.cond)
        cond = self.llvm.expr(if_.cond).r_val
        with self.builder.if_else(cond) as (then_do, else_do):
            with then_do:
                self.visit_stmt(if_.then_do)
            with else_do:
                self.visit_stmt(if_.else_do)

    def visit_while(self, while_: WhileStmtIR):
        cond = self.builder.append_basic_block()
        body = self.builder.append_basic_block()
        after = self.builder.append_basic_block()

        self.builder.branch(cond)

        with self.builder.goto_block(cond):
            self.visit_expr(while_.cond)
            cond_val = self.llvm.expr(while_.cond).r_val
            self.builder.cbranch(cond_val, body, after)

        with self.builder.goto_block(body):
            self.visit_stmt(while_.while_do)
            if not self.builder.block.is_terminated:
                self.builder.branch(cond)

        self.builder.position_at_start(after)

    def visit_expr_stmt(self, stmt: ExprStmtIR):
        self.visit_expr(stmt.expr)

    def visit_var_decl(self, decl: VarDeclIR):
        llvm_type = self.resolve_type(self.symbols.decl(decl).type)
        llvm_val = self.builder.alloca(llvm_type)

        self.visit_expr(decl.value)
        expr_val = self.llvm.expr(decl.value).r_val
        self.builder.store(expr_val, llvm_val)

        self.llvm.decl(decl, set_to=LLVMData.DeclData(llvm_val, is_ptr=True))

    def visit_block(self, block: BlockIR):
        for stmt in block.stmts:
            self.visit_stmt(stmt)

    def visit_return(self, ret: ReturnIR):
        expr = ret.expr
        self.visit_expr(expr)
        llvm_val = self.llvm.expr(expr).r_val
        self.builder.ret(llvm_val)

    def visit_compare(self, cmp: CompareIR):
        self.visit_expr(cmp.left)
        self.visit_expr(cmp.right)
        is_signed = self.symbols.compare(cmp).is_signed
        left = self.llvm.expr(cmp.left).r_val
        right = self.llvm.expr(cmp.right).r_val
        if is_signed:
            llvm_val = self.builder.icmp_signed(cmp.op, left, right)
        else:
            llvm_val = self.builder.icmp_unsigned(cmp.op, left, right)
        self.llvm.expr(cmp, set_to=LLVMData.ExprData(None, llvm_val))

    def visit_arithmetic(self, arith: ArithmeticIR):
        self.visit_expr(arith.left)
        self.visit_expr(arith.right)
        is_signed = self.symbols.arithmetic(arith).is_signed
        left = self.llvm.expr(arith.left).r_val
        right = self.llvm.expr(arith.right).r_val
        if arith.op == '+':
            llvm_val = self.builder.add(left, right)
        elif arith.op == '-':
            llvm_val = self.builder.sub(left, right)
        elif arith.op == '*':
            llvm_val = self.builder.mul(left, right)
        else:
            raise NotImplementedError()
        self.llvm.expr(arith, set_to=LLVMData.ExprData(None, llvm_val))

    def visit_negate(self, negate: NegateIR):
        self.visit_expr(negate.right)
        right = self.llvm.expr(negate.right).r_val
        llvm_val = self.builder.neg(right)
        self.llvm.expr(negate, set_to=LLVMData.ExprData(None, llvm_val))

    def visit_int(self, num: IntIR):
        # TODO add bit-size symbol data for int so resolve type is not needed
        llvm_type = self.resolve_type(self.symbols.expr(num).return_type)
        self.llvm.expr(num, set_to=LLVMData.ExprData(None, ir.Constant(llvm_type, num.num)))

    def visit_call(self, call: CallIR):
        self.visit_expr(call.callee)
        callee_val = self.llvm.expr(call.callee).r_val
        arg_vals = []
        for arg in call.arguments:
            self.visit_expr(arg)
            arg_val = self.llvm.expr(arg).r_val
            arg_vals.append(arg_val)

        llvm_val = self.builder.call(callee_val, arg_vals)

        self.llvm.expr(call, LLVMData.ExprData(None, llvm_val))

    def visit_new(self, new: NewIR):
        struct_type = self.symbols.type(new.type).resolved_type

        llvm_val = ir.Constant(self.resolve_type(struct_type), ir.Undefined)
        for index, arg in enumerate(new.arguments):
            self.visit_expr(arg)
            arg_val = self.llvm.expr(arg).r_val
            llvm_val = self.builder.insert_value(llvm_val, arg_val, index)

        self.llvm.expr(new, set_to=LLVMData.ExprData(None, llvm_val))

    def visit_get_var(self, get_var: GetVarIR):
        symbol = self.symbols.get_var(get_var).symbol
        is_function = self.symbols.get_var(get_var).is_function
        decl_data = self.llvm.decl(symbol.declarer)
        if decl_data.is_ptr:
            var_ptr = decl_data.var_value
            llvm_val = self.builder.load(var_ptr)
        else:
            var_ptr = None
            llvm_val = decl_data.var_value
        self.llvm.expr(get_var, LLVMData.ExprData(var_ptr, llvm_val))

    def visit_set_var(self, set_var: SetVarIR):
        symbol = self.symbols.set_var(set_var).symbol
        var_ptr = self.llvm.decl(symbol.declarer).var_value

        self.visit_expr(set_var.value)
        expr_val = self.llvm.expr(set_var.value).r_val

        self.builder.store(expr_val, var_ptr)

        self.llvm.expr(set_var, set_to=LLVMData.ExprData(var_ptr, expr_val))

    def visit_get_attr(self, get_attr: GetAttrIR):
        struct_type = self.symbols.get_attr(get_attr).struct_type
        index = self.symbols.get_attr(get_attr).index

        self.visit_expr(get_attr.obj)
        struct_ptr = self.llvm.expr(get_attr.obj).l_val
        if struct_ptr is None:
            struct_val = self.llvm.expr(get_attr.obj).r_val
            field_ptr = None
            llvm_val = self.builder.extract_value(struct_val, index)
        else:
            field_ptr = self.builder.gep(struct_ptr, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), index)])
            llvm_val = self.builder.load(field_ptr)

        self.llvm.expr(get_attr, set_to=LLVMData.ExprData(field_ptr, llvm_val))

    def visit_set_attr(self, set_attr: SetAttrIR):
        struct_type = self.symbols.set_attr(set_attr).struct_type
        index = self.symbols.set_attr(set_attr).index

        self.visit_expr(set_attr.obj)
        struct_ptr = self.llvm.expr(set_attr.obj).l_val
        field_ptr = self.builder.gep(struct_ptr, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), index)])

        self.visit_expr(set_attr.value)
        value = self.llvm.expr(set_attr.value).r_val
        value_lval = self.llvm.expr(set_attr.value).l_val
        self.builder.store(value, field_ptr)

        self.llvm.expr(set_attr, set_to=LLVMData.ExprData(value_lval, value))

    def visit_get_static_attr_expr(self, get_static: GetStaticAttrExprIR):
        value = self.symbols.get_static_attr_expr(get_static).resolved_value
        decl_data = self.llvm.decl(value.declarer)
        if decl_data.is_ptr:
            var_ptr = decl_data.var_value
            llvm_val = self.builder.load(var_ptr)
        else:
            var_ptr = None
            llvm_val = decl_data.var_value

        self.llvm.expr(get_static, set_to=LLVMData.ExprData(var_ptr, llvm_val))

    def visit_get_type(self, type: GetTypeIR):
        resolved: TypeSymbol = self.symbols.type(type).resolved_type
        llvm_type = self.resolve_type(resolved)
        self.llvm.type(type, set_to=LLVMData.TypeData(llvm_type))

    def visit_intrinsic(self, intrinsic: IntrinsicIR):
        if intrinsic.name in ('int8', 'int32', 'int64'):
            num = intrinsic.args[0]
            from_type = cast(IntTypeSymbol, self.symbols.expr(num).return_type)
            to_type = cast(IntTypeSymbol, self.symbols.expr(intrinsic).return_type)
            self.visit_expr(num)
            num_val = self.llvm.expr(num).r_val
            if from_type.bit_size > to_type.bit_size:
                llvm_val = self.builder.trunc(num_val, self.resolve_type(to_type))
            else:
                llvm_val = self.builder.zext(num_val, self.resolve_type(to_type))

            self.llvm.expr(intrinsic, set_to=LLVMData.ExprData(None, llvm_val))
        else:
            raise Exception()


class LLVMBackend(CBackend):
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
            return super().handle_option(option)

    @staticmethod
    def create_function_passes(llvm_mod: llvm.ModuleRef, machine: llvm.TargetMachine):
        fpmb = llvm.create_pass_manager_builder()
        fpmb.opt_level = 3
        fpmb.inlining_threshold = 225

        fpm = llvm.create_function_pass_manager(llvm_mod)
        machine.add_analysis_passes(fpm)
        fpmb.populate(fpm)
        fpm.add_dead_code_elimination_pass()
        fpm.add_cfg_simplification_pass()
        fpm.add_instruction_combining_pass()
        fpm.add_licm_pass()
        fpm.add_sccp_pass()
        fpm.add_sroa_pass()
        fpm.add_type_based_alias_analysis_pass()
        fpm.add_basic_alias_analysis_pass()

        return fpm

    @staticmethod
    def create_module_passes(machine: llvm.TargetMachine):
        pmb = llvm.create_pass_manager_builder()
        pmb.inlining_threshold = 225

        pm = llvm.ModulePassManager()
        machine.add_analysis_passes(pm)
        pmb.populate(pm)

        return pm

    def run_backend(self):
        if self.output_path is None:
            output_form = Path.cwd() / Path("a")
            output_path = output_form.with_suffix(".exe")
            self.output_path = output_path
        else:
            output_form = self.output_path.absolute().with_suffix("")
            output_path = self.output_path

        target = llvm.Target.from_default_triple()
        machine = target.create_target_machine(codemodel='small')
        self.llvm_ir.triple = target.triple

        llvm_mod = llvm.parse_assembly(str(self.llvm_ir))

        if self.opt_level >= 1:
            for func in llvm_mod.functions:
                fpm = self.create_function_passes(llvm_mod, machine)
                fpm.initialize()
                fpm.run(func)
                fpm.finalize()

            pm = self.create_module_passes(machine)
            pm.run(llvm_mod)

        if self.emit_llvm:
            llvm_file = self.output_path.with_suffix(".ll")
            with llvm_file.open("w") as file:
                file.write(str(llvm_mod))

        object_data = machine.emit_object(llvm_mod)

        if (temp_path := output_form.with_suffix(".o")).exists():
            i = 0
            while (temp_path := Path(str(output_form) + f"_{i}").with_suffix(".o")).exists():
                i += 1

        with temp_path.open("wb") as out:
            out.write(object_data)

        try:
            linker = self.linker_cls([temp_path], output_path)
            linker.link_files()
        finally:
            temp_path.unlink()
            MessageHandler.flush_messages()

    def run_output(self):
        return_code = CLinker.process_call([self.output_path])
        print("Returned with code:", return_code.returncode)
        return return_code
