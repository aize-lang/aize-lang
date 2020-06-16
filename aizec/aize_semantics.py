from __future__ import annotations

from aizec.common import *

from aizec.aize_ir import *
from aizec.aize_ir_pass import IRTreePass, IRPassSequence, PassesRegister, PassAlias

from aizec.aize_error import AizeMessage, Reporter, MessageHandler, ErrorLevel
from aizec.aize_source import *
from aizec.aize_symbols import *


# region Errors
# TODO Errors could be unified into one class with multiple constructors
class DefinitionError(AizeMessage):
    def __init__(self, msg: str, pos: Position, note: AizeMessage = None):
        super().__init__(ErrorLevel.ERROR)
        self.msg = msg
        self.pos = pos

        self.note = note

    @classmethod
    def name_existing(cls, node: TextIR, existing: Symbol):
        note = DefinitionNote.from_pos(existing.position, "Previously declared here")
        error = cls.from_node(node, f"Name '{existing.name}' already declared in this scope", note)
        return error

    @classmethod
    def name_undefined(cls, node: TextIR, name: str):
        error = cls.from_node(node, f"Name '{name}' could not be found")
        return error

    @classmethod
    def param_repeated(cls, func: FunctionIR, param: ParamIR, name: str):
        note = DefinitionNote.from_node(param, "Repeated here")
        error = cls.from_node(func, f"Parameter name '{name}' repeated", note)
        return error

    @classmethod
    def field_not_found(cls, field_name: str, accessor: Position, struct_type: StructTypeSymbol):
        note = DefinitionNote.from_pos(struct_type.position, f"{struct_type} defined here")
        error = cls(f"Field '{field_name}' not found on {struct_type}", accessor)
        return error

    @classmethod
    def field_repeated(cls, repeat: Position, original: Position, name: str):
        note = DefinitionNote.from_pos(original, "Previously declared here")
        error = cls.from_pos(repeat, f"Field name '{name}' repeated", note)
        return error

    @classmethod
    def from_pos(cls, pos: Position, msg: str, note: AizeMessage = None):
        return cls(msg, pos, note)

    @classmethod
    def from_node(cls, node: TextIR, msg: str, note: AizeMessage = None):
        return cls.from_pos(node.pos, msg, note)

    def display(self, reporter: Reporter):
        reporter.positioned_error("Name Resolution Error", self.msg, self.pos)
        if self.note is not None:
            reporter.separate()
            with reporter.indent():
                self.note.display(reporter)


class DefinitionNote(AizeMessage):
    def __init__(self, msg: str, pos: Position):
        super().__init__(ErrorLevel.NOTE)
        self.msg = msg
        self.pos = pos

    @classmethod
    def from_node(cls, node: TextIR, msg: str):
        return cls.from_pos(node.pos, msg)

    @classmethod
    def from_pos(cls, pos: Position, msg: str):
        return cls(msg, pos)

    def display(self, reporter: Reporter):
        reporter.positioned_error("Note", self.msg, self.pos)


class TypeCheckingError(AizeMessage):
    def __init__(self, msg: str, pos: Position, notes: List[AizeMessage] = None):
        super().__init__(ErrorLevel.ERROR)
        self.pos = pos
        self.msg = msg

        self.notes = [] if notes is None else notes

    @classmethod
    def from_nodes(cls, offender: TextIR, definition: TextIR, expected: TypeSymbol, got: TypeSymbol):
        note = DefinitionNote.from_pos(definition.pos, "Declared here")
        error = cls(f"Expected type {expected}, got type {got}", offender.pos, [note])
        return error

    @classmethod
    def from_node(cls, offender: TextIR, expected: TypeSymbol, got: TypeSymbol):
        error = cls(f"Expected type {expected}, got type {got}", offender.pos)
        return error

    @classmethod
    def function_callee(cls, callee: TextIR, got: TypeSymbol):
        error = cls(f"Expected a function to call, got {got}", callee.pos)
        return error

    @classmethod
    def too_many_arguments(cls, expected_args: int, got_args: int, first_excess: Position):
        if expected_args == 1:
            error = cls(f"Expected {expected_args} argument, but got {got_args-expected_args} extra", first_excess)
        else:
            error = cls(f"Expected {expected_args} arguments, but got {got_args-expected_args} extra", first_excess)
        return error

    @classmethod
    def too_few_arguments(cls, expected_args: int, got_args: int, call: Position):
        if expected_args == 1:
            error = cls(f"Expected {expected_args} argument, but got {expected_args-got_args} too few", call)
        else:
            error = cls(f"Expected {expected_args} arguments, but got {expected_args-got_args} too few", call)
        return error

    @classmethod
    def expected_type(cls, expected: TypeSymbol, got: TypeSymbol, where: Position, declaration: Position):
        note = DefinitionNote(f"Expected type declared here", declaration)
        error = cls(f"Expected type {expected}, got type {got}", where, [note])
        return error

    @classmethod
    def expected_return_type(cls, expected: TypeSymbol, got: TypeSymbol, where: Position, definition: Position):
        note = DefinitionNote(f"Return type declared here", definition)
        error = cls(f"Expected type {expected}, got type {got}", where, [note])
        return error

    @classmethod
    def expected_type_cls(cls, expecting_name: str, offending_node: TextIR, cls_name: str, got: TypeSymbol):
        error = cls(f"{expecting_name} expected {cls_name}, got {got}", offending_node.pos)
        return error

    def display(self, reporter: Reporter):
        reporter.positioned_error("Type Checking Error", self.msg, self.pos)
        for note in self.notes:
            reporter.separate()
            with reporter.indent():
                note.display(reporter)


class MismatchedTypesError(AizeMessage):
    def __init__(self, msg: str, pos: Position):
        super().__init__(ErrorLevel.ERROR)
        self.msg = msg
        self.pos = pos

    def display(self, reporter: Reporter):
        reporter.positioned_error("Control Flow Error", self.msg, self.pos)


class FlowError(AizeMessage):
    def __init__(self, msg: str, pos: Position):
        super().__init__(ErrorLevel.ERROR)
        self.msg = msg
        self.pos = pos

    def display(self, reporter: Reporter):
        reporter.positioned_error("Control Flow Error", self.msg, self.pos)
# endregion


DefaultPasses = IRPassSequence("DefaultPasses")
PassesRegister.register(DefaultPasses)


class LiteralData(Extension):
    class BuiltinData:
        def __init__(self,
                     uint: Dict[int, TypeSymbol],
                     sint: Dict[int, TypeSymbol],
                     puts: VariableSymbol):
            self.uint = uint
            self.sint = sint
            self.puts = puts

    def general(self, set_to: BuiltinData = None) -> BuiltinData:
        return super().general(set_to)

    def program(self, node: ProgramIR, set_to=None):
        raise NotImplementedError()

    def source(self, node: SourceIR, set_to=None):
        raise NotImplementedError()

    def function(self, node: FunctionIR, set_to=None):
        raise NotImplementedError()

    def param(self, node: ParamIR, set_to=None):
        raise NotImplementedError()

    def stmt(self, node: StmtIR, set_to=None):
        raise NotImplementedError()

    def expr(self, node: ExprIR, set_to=None):
        raise NotImplementedError()

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

    def type(self, node: TypeIR, set_to=None):
        raise NotImplementedError()


class SymbolData(Extension):
    def general(self, set_to=None):
        raise NotImplementedError()

    class ProgramData:
        def __init__(self, builtins: NamespaceSymbol):
            self.builtins = builtins

    def program(self, node: ProgramIR, set_to: ProgramData = None) -> ProgramData:
        return super().program(node, set_to)

    class SourceData:
        def __init__(self, globals: NamespaceSymbol):
            self.globals = globals

    def source(self, node: SourceIR, set_to: SourceData = None) -> SourceData:
        return super().source(node, set_to)

    class FunctionData:
        def __init__(self, symbol: VariableSymbol, namespace: NamespaceSymbol):
            self.symbol = symbol
            self.namespace = namespace

    def function(self, node: FunctionIR, set_to: FunctionData = None) -> FunctionData:
        return super().function(node, set_to)

    class ParamData:
        def __init__(self, symbol: VariableSymbol):
            self.symbol = symbol

    def param(self, node: ParamIR, set_to: ParamData = None) -> ParamData:
        return super().param(node, set_to)

    class StmtData:
        def __init__(self, is_terminal: bool):
            self.is_terminal = is_terminal

    def stmt(self, node: StmtIR, set_to: StmtData = None) -> StmtData:
        return super().stmt(node, set_to)

    class ExprData:
        def __init__(self, return_type: TypeSymbol, is_lval: bool):
            self.return_type: TypeSymbol = return_type
            self.is_lval = is_lval

    def expr(self, node: ExprIR, set_to: ExprData = None) -> ExprData:
        return super().expr(node, set_to)

    class CompareData:
        def __init__(self, is_signed: bool):
            self.is_signed = is_signed

    def compare(self, node: CompareIR, set_to: CompareData = None) -> CompareData:
        return super().compare(node, set_to)

    class ArithmeticData:
        def __init__(self, is_signed: bool):
            self.is_signed = is_signed

    def arithmetic(self, node: ArithmeticIR, set_to: ArithmeticData = None) -> ArithmeticData:
        return super().arithmetic(node, set_to)

    class GetVarData:
        def __init__(self, symbol: VariableSymbol, is_function: bool):
            self.symbol = symbol
            self.is_function = is_function

    def get_var(self, node: GetVarIR, set_to: GetVarData = None) -> GetVarData:
        return super().get_var(node, set_to)

    class SetVarData:
        def __init__(self, symbol: VariableSymbol):
            self.symbol = symbol

    def set_var(self, node: SetVarIR, set_to: SetVarData = None) -> SetVarData:
        return super().set_var(node, set_to)

    class GetAttrData:
        def __init__(self, struct_type: Optional[StructTypeSymbol], index: Optional[int]):
            self.struct_type = struct_type
            self.index = index

    def get_attr(self, node: GetAttrIR, set_to: GetAttrData = None) -> GetAttrData:
        return super().get_attr(node, set_to)

    class TypeData:
        def __init__(self, resolved_type: TypeSymbol):
            self.resolved_type: TypeSymbol = resolved_type

    def type(self, node: TypeIR, set_to: TypeData = None) -> TypeData:
        return super().type(node, set_to)

    # region Extension Extensions
    class DeclData:
        def __init__(self, declarer: NodeIR, declares: VariableSymbol, type: TypeSymbol):
            self.declarer = declarer
            self.declares = declares
            self.type = type

    def decl(self, node: NodeIR, set_to: DeclData = None) -> DeclData:
        return super().ext(node, 'decl', set_to)
    # endregion


class IRSymbolsPass(IRTreePass, ABC):
    def __init__(self, ir: IR):
        super().__init__(ir)
        self._table = SymbolTable()

    def was_successful(self) -> bool:
        MessageHandler.flush_messages()
        return True

    def enter_namespace(self, namespace: NamespaceSymbol):
        if namespace.namespace is not None:
            if namespace.namespace is not self.current_namespace:
                raise ValueError("When entering a namespace, it must be a child of the current namespace")
        return self._table.enter(namespace)

    @property
    def current_namespace(self) -> NamespaceSymbol:
        return self._table.current_namespace


@PassesRegister.register(to_sequences=[DefaultPasses])
class InitSymbols(IRSymbolsPass):
    def __init__(self, ir: IR):
        super().__init__(ir)

        self.builtins: LiteralData = self.add_ext(LiteralData)
        self.symbols: SymbolData = self.add_ext(SymbolData)

    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return set()

    @classmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        return set()

    def visit_program(self, program: ProgramIR):
        builtin_namespace = NamespaceSymbol("<builtins>", Position.new_none())
        self.symbols.program(program, set_to=SymbolData.ProgramData(builtin_namespace))

        def def_int(name, signed, bits):
            i = IntTypeSymbol(name, signed, bits, Position.new_none())
            builtin_namespace.define_type(i)
            return i

        uint1 = def_int("bool", False, 1)
        uint8 = def_int("uint8", False, 8)
        uint32 = def_int("uint32", False, 32)
        uint64 = def_int("uint64", False, 64)

        int8 = def_int("int8", True, 8)
        int32 = def_int("int32", True, 32)
        int64 = def_int("int64", True, 64)

        puts_type = FunctionTypeSymbol([int32], int32, Position.new_none())
        puts = VariableSymbol("puts", program, puts_type, Position.new_none())
        builtin_namespace.define_value(puts)

        self.builtins.general(set_to=LiteralData.BuiltinData({1: uint1, 8: uint8, 32: uint32, 64: uint64},
                                                             {8: int8, 32: int32, 64: int64},
                                                             puts))

        with self.enter_namespace(builtin_namespace):
            for source in program.sources:
                self.visit_source(source)

    def visit_source(self, source: SourceIR):
        global_namespace = NamespaceSymbol(f"<{source.source_name} globals>", Position.new_source(source.source_name))
        self.current_namespace.define_namespace(global_namespace, visible=False)
        self.symbols.source(source, set_to=SymbolData.SourceData(global_namespace))


@PassesRegister.register(to_sequences=[DefaultPasses])
class DeclareTypes(IRSymbolsPass):
    def __init__(self, ir: IR):
        super().__init__(ir)

        self.symbols = self.get_ext(SymbolData)
        self.builtins: LiteralData = self.get_ext(LiteralData)

    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return {InitSymbols}

    @classmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        return {LiteralData, SymbolData}

    def visit_program(self, program: ProgramIR):
        with self.enter_namespace(self.symbols.program(program).builtins):
            for source in program.sources:
                self.visit_source(source)

    def visit_source(self, source: SourceIR):
        with self.enter_namespace(self.symbols.source(source).globals):
            for top_level in source.top_levels:
                self.visit_top_level(top_level)

    def visit_struct(self, struct: StructIR):
        fields: Dict[str, TypeSymbol] = {}
        field_pos: Dict[str, Position] = {}
        for field in struct.fields:
            if field.name in fields:
                msg = DefinitionError.field_repeated(field.pos, field_pos[field.name], field.name)
                MessageHandler.handle_message(msg)
            else:
                self.visit_type(field.type)
                fields[field.name] = self.symbols.type(field.type).resolved_type
                field_pos[field.name] = field.pos
        struct_type = StructTypeSymbol(struct.name, fields, struct.pos, field_pos)
        self.current_namespace.define_type(struct_type)

    def visit_get_type(self, type: GetTypeIR):
        try:
            resolved_type = self.current_namespace.lookup_type(type.name)
        except FailedLookupError as err:
            msg = DefinitionError.name_undefined(type, err.failed_name)
            MessageHandler.handle_message(msg)
            resolved_type = ErroredTypeSymbol(type.pos)
        self.symbols.type(type, SymbolData.TypeData(resolved_type))


@PassesRegister.register(to_sequences=[DefaultPasses])
class ResolveTypes(IRSymbolsPass):
    def __init__(self, ir: IR):
        super().__init__(ir)
        self._current_func: Optional[FunctionIR] = None
        self._current_func_type: Optional[FunctionTypeSymbol] = None

        self.builtins: LiteralData = self.get_ext(LiteralData)
        self.symbols: SymbolData = self.get_ext(SymbolData)

    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return {InitSymbols, DeclareTypes}

    @classmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        return {LiteralData, SymbolData}

    @property
    def current_func(self):
        if self._current_func is not None:
            return self._current_func
        else:
            raise ValueError("Not in a function")

    @property
    def current_func_type(self):
        if self._current_func_type is not None:
            return self._current_func_type
        else:
            raise ValueError("Not in a function")

    @contextmanager
    def in_function(self, func: FunctionIR, type: FunctionTypeSymbol):
        old_func, self._current_func = self._current_func, func
        old_type, self._current_func_type = self._current_func_type, type
        with self.enter_namespace(self.symbols.function(func).namespace):
            yield
        self._current_func = old_func
        self._current_func_type = old_type

    def visit_program(self, program: ProgramIR):
        with self.enter_namespace(self.symbols.program(program).builtins):
            for source in program.sources:
                self.visit_source(source)

    def visit_source(self, source: SourceIR):
        with self.enter_namespace(self.symbols.source(source).globals):
            for top_level in source.top_levels:
                self.visit_top_level(top_level)

    def visit_function(self, func: FunctionIR):
        for param in func.params:
            self.visit_param(param)
        self.visit_type(func.ret)
        params = [self.symbols.type(param.type).resolved_type for param in func.params]
        ret = self.symbols.type(func.ret).resolved_type
        func_type = FunctionTypeSymbol(params, ret, func.pos)

        func_value = VariableSymbol(func.name, func, func_type, func.pos)
        try:
            self.current_namespace.define_value(func_value)
        except DuplicateSymbolError as err:
            msg = DefinitionError.name_existing(func, err.old_symbol)
            MessageHandler.handle_message(msg)

        func_namespace = NamespaceSymbol(f"<{func.name} body>", func.pos)
        self.current_namespace.define_namespace(func_namespace, visible=False)
        self.symbols.function(func, set_to=SymbolData.FunctionData(func_value, func_namespace))
        self.symbols.decl(func, set_to=SymbolData.DeclData(func, func_value, func_type))

        with self.in_function(func, func_type):
            for param in func.params:
                try:
                    func_namespace.define_value(self.symbols.param(param).symbol)
                except DuplicateSymbolError as err:
                    msg = DefinitionError.param_repeated(func, param, param.name)
                    MessageHandler.handle_message(msg)

        is_terminated = False
        with self.in_function(func, func_type):
            for stmt in func.body:
                self.visit_stmt(stmt)
                stmt_terminates = self.symbols.stmt(stmt).is_terminal
                if stmt_terminates:
                    if not is_terminated:
                        is_terminated = True
                    else:
                        # TODO Error
                        is_terminated = True
        # TODO if return is void or (), then it does not need to be terminated
        if not is_terminated:
            msg = FlowError("Function ends without always terminating", func.pos)
            MessageHandler.handle_message(msg)

    def visit_struct(self, struct: StructIR):
        pass

    def visit_param(self, param: ParamIR):
        self.visit_type(param.type)
        symbol = VariableSymbol(param.name, param, self.symbols.type(param.type).resolved_type, param.pos)
        self.symbols.param(param, set_to=SymbolData.ParamData(symbol))

    def visit_if(self, if_: IfStmtIR):
        self.visit_expr(if_.cond)
        expected = self.builtins.general().uint[1]
        got = self.symbols.expr(if_.cond).return_type
        if expected.is_super_of(got):
            pass
        elif isinstance(got, ErroredTypeSymbol):
            pass
        else:
            msg = TypeCheckingError.from_node(if_.cond, expected, got)
            MessageHandler.handle_message(msg)
        self.visit_stmt(if_.else_do)
        self.visit_stmt(if_.then_do)
        is_terminal = self.symbols.stmt(if_.else_do).is_terminal and self.symbols.stmt(if_.then_do).is_terminal
        self.symbols.stmt(if_, set_to=SymbolData.StmtData(is_terminal))

    def visit_expr_stmt(self, stmt: ExprStmtIR):
        self.visit_expr(stmt.expr)
        self.symbols.stmt(stmt, set_to=SymbolData.StmtData(is_terminal=False))

    def visit_var_decl(self, decl: VarDeclIR):
        self.visit_ann(decl.ann)
        var_type = self.symbols.type(decl.ann.type).resolved_type

        self.visit_expr(decl.value)
        value_type = self.symbols.expr(decl.value).return_type

        if self.check_error_type(var_type, value_type):
            pass
        else:
            if var_type.is_super_of(value_type):
                pass
            else:
                msg = TypeCheckingError.expected_type(var_type, value_type, decl.value.pos, decl.pos)
                MessageHandler.handle_message(msg)

        symbol = VariableSymbol(decl.name, decl, var_type, decl.pos)
        try:
            self.current_namespace.define_value(symbol)
        except DuplicateSymbolError as err:
            msg = DefinitionError.name_existing(decl, err.old_symbol)
            MessageHandler.handle_message(msg)

        self.symbols.decl(decl, set_to=SymbolData.DeclData(decl, symbol, var_type))
        self.symbols.stmt(decl, set_to=SymbolData.StmtData(is_terminal=False))

    def visit_block(self, block: BlockIR):
        # TODO scope
        block_is_terminal = False
        for stmt in block.stmts:
            self.visit_stmt(stmt)
            stmt_is_terminal = self.symbols.stmt(stmt).is_terminal
            if stmt_is_terminal:
                if not block_is_terminal:
                    block_is_terminal = True
                else:
                    # TODO ERROR (multiple returns, unreachable)
                    block_is_terminal = True
        self.symbols.stmt(block, set_to=SymbolData.StmtData(block_is_terminal))

    def visit_return(self, ret: ReturnIR):
        self.visit_expr(ret.expr)
        expected = self.current_func_type.ret
        got = self.symbols.expr(ret.expr).return_type
        if expected.is_super_of(got):
            pass
        elif isinstance(got, ErroredTypeSymbol) or isinstance(expected, ErroredTypeSymbol):
            pass
        else:
            msg = TypeCheckingError.expected_return_type(expected, got, ret.expr.pos, self.current_func.ret.pos)
            MessageHandler.handle_message(msg)
        self.symbols.stmt(ret, set_to=SymbolData.StmtData(True))

    def check_error_type(self, *types: TypeSymbol) -> Optional[TypeSymbol]:
        for type in types:
            if isinstance(type, ErroredTypeSymbol):
                return type
        return None

    def visit_compare(self, cmp: CompareIR):
        self.visit_expr(cmp.left)
        self.visit_expr(cmp.right)
        left = self.symbols.expr(cmp.left).return_type
        right = self.symbols.expr(cmp.right).return_type

        is_signed = False
        if errored_type := self.check_error_type():
            return_type = errored_type
        else:
            for node, node_type in [(cmp.left, left), (cmp.right, right)]:
                if not isinstance(node_type, IntTypeSymbol):
                    msg = TypeCheckingError.expected_type_cls("Comparison", node, "integers", node_type)
                    MessageHandler.handle_message(msg)
                    return_type = ErroredTypeSymbol(cmp.pos)
                    break
            else:
                left, right = cast(IntTypeSymbol, left), cast(IntTypeSymbol, right)
                if left.is_signed == right.is_signed:
                    is_signed = left.is_signed
                    return_type = self.builtins.general().uint[1]
                else:
                    left_note = DefinitionNote(f"Left is of type {left}", cmp.left.pos)
                    right_note = DefinitionNote(f"Right is of type {right}", cmp.right.pos)
                    msg = TypeCheckingError("Signed and Unsigned Integers cannot be mixed in comparison operations",
                                            cmp.pos, [left_note, right_note])
                    MessageHandler.handle_message(msg)
                    return_type = ErroredTypeSymbol(cmp.pos)
                
        self.symbols.expr(cmp, SymbolData.ExprData(return_type, False))
        self.symbols.compare(cmp, SymbolData.CompareData(is_signed))

    def visit_arithmetic(self, arith: ArithmeticIR):
        self.visit_expr(arith.left)
        self.visit_expr(arith.right)
        left = self.symbols.expr(arith.left).return_type
        right = self.symbols.expr(arith.right).return_type

        return_type: TypeSymbol
        is_signed = False
        if errored_type := self.check_error_type(left, right):
            return_type = errored_type
        else:
            for node, node_type in [(arith.left, left), (arith.right, right)]:
                if not isinstance(node_type, IntTypeSymbol):
                    msg = TypeCheckingError.expected_type_cls("Arithmetic", node, "integers", node_type)
                    MessageHandler.handle_message(msg)
                    return_type = ErroredTypeSymbol(arith.pos)
                    break
            else:
                left, right = cast(IntTypeSymbol, left), cast(IntTypeSymbol, right)
                if left.is_signed == right.is_signed:
                    is_signed = left.is_signed
                    return_type = max(left, right, key=lambda t: t.bit_size)
                else:
                    left_note = DefinitionNote(f"Left is of type {left}", arith.left.pos)
                    right_note = DefinitionNote(f"Right is of type {right}", arith.right.pos)
                    msg = TypeCheckingError("Signed and Unsigned Integers cannot be mixed in arithmetic operations", arith.pos, [left_note, right_note])
                    MessageHandler.handle_message(msg)
                    return_type = ErroredTypeSymbol(arith.pos)

        self.symbols.expr(arith, SymbolData.ExprData(return_type, False))
        self.symbols.arithmetic(arith, SymbolData.ArithmeticData(is_signed))

    def visit_new(self, new: NewIR):
        self.visit_type(new.type)
        type = self.symbols.type(new.type).resolved_type

        return_type: TypeSymbol
        is_struct = False
        if return_type := self.check_error_type(type):
            pass
        else:
            if isinstance(type, StructTypeSymbol):
                return_type = type
                is_struct = True
            else:
                msg = TypeCheckingError.expected_type_cls("new", new.type, "a struct", type)
                MessageHandler.handle_message(msg)
                return_type = ErroredTypeSymbol(new.pos)

        for arg in new.arguments:
            self.visit_expr(arg)

        if is_struct:
            struct_type = cast(StructTypeSymbol, type)
            for arg, field, field_pos in zip(new.arguments, struct_type.fields.values(), struct_type.field_pos.values()):
                arg_type = self.symbols.expr(arg).return_type
                if field.is_super_of(arg_type):
                    pass
                else:
                    msg = TypeCheckingError.expected_type(field, arg_type, arg.pos, field_pos)
                    MessageHandler.handle_message(msg)

            expected_count = len(struct_type.fields)
            got_count = len(new.arguments)
            if got_count > expected_count:
                excess = new.arguments[got_count-expected_count]
                msg = TypeCheckingError.too_many_arguments(expected_count, got_count, excess.pos)
                MessageHandler.handle_message(msg)
            elif got_count < expected_count:
                msg = TypeCheckingError.too_few_arguments(expected_count, got_count, new.pos)
                MessageHandler.handle_message(msg)

        self.symbols.expr(new, set_to=SymbolData.ExprData(return_type, False))

    def visit_call(self, call: CallIR):
        self.visit_expr(call.callee)
        for arg in call.arguments:
            self.visit_expr(arg)
        callee_type = self.symbols.expr(call.callee).return_type
        arg_types = [self.symbols.expr(arg).return_type for arg in call.arguments]

        # TODO argument checking, maybe when zip-strict is a thing

        # TODO create a single function for this
        if isinstance(callee_type, FunctionTypeSymbol):
            return_type = callee_type.ret
        elif isinstance(callee_type, ErroredTypeSymbol):
            return_type = callee_type
        else:
            msg = TypeCheckingError.function_callee(call.callee, callee_type)
            MessageHandler.handle_message(msg)
            return_type = ErroredTypeSymbol(call.pos)

        self.symbols.expr(call, SymbolData.ExprData(return_type, False))

    def visit_get_var(self, get_var: GetVarIR):
        try:
            value = self.current_namespace.lookup_value(get_var.var_name)
        except FailedLookupError:
            msg = DefinitionError.name_undefined(get_var, get_var.var_name)
            MessageHandler.handle_message(msg)
            value = ErroredVariableSymbol(get_var, get_var.pos)
        is_function = isinstance(value.type, FunctionTypeSymbol)
        self.symbols.expr(get_var, SymbolData.ExprData(value.type, is_lval=is_function))
        self.symbols.get_var(get_var, set_to=SymbolData.GetVarData(value, is_function))

    def visit_set_var(self, set_var: SetVarIR):
        try:
            variable = self.current_namespace.lookup_value(set_var.var_name)
        except FailedLookupError:
            msg = DefinitionError.name_undefined(set_var, set_var.var_name)
            MessageHandler.handle_message(msg)
            variable = ErroredVariableSymbol(set_var, set_var.pos)
        variable_type = variable.type

        self.visit_expr(set_var.value)
        value_type = self.symbols.expr(set_var.value).return_type

        return_type: TypeSymbol
        if return_type := self.check_error_type(variable_type, value_type):
            pass
        else:
            if variable_type.is_super_of(value_type):
                return_type = value_type
            else:
                msg = TypeCheckingError.expected_type(variable_type, value_type, set_var.pos, variable.position)
                MessageHandler.handle_message(msg)
                return_type = ErroredTypeSymbol(set_var.pos)

        self.symbols.expr(set_var, set_to=SymbolData.ExprData(return_type, True))
        self.symbols.set_var(set_var, set_to=SymbolData.SetVarData(variable))

    def visit_get_attr(self, get_attr: GetAttrIR):
        self.visit_expr(get_attr.obj)
        obj_type = self.symbols.expr(get_attr.obj).return_type
        obj_is_lval = self.symbols.expr(get_attr.obj).is_lval

        return_type: TypeSymbol
        is_struct = False
        if return_type := self.check_error_type(obj_type):
            pass
        else:
            if isinstance(obj_type, StructTypeSymbol):
                is_struct = True
            else:
                msg = TypeCheckingError.expected_type_cls("get attribute", get_attr.obj, "a struct", obj_type)
                MessageHandler.handle_message(msg)
                return_type = ErroredTypeSymbol(get_attr.pos)

        if is_struct:
            struct_type = cast(StructTypeSymbol, obj_type)
            if get_attr.attr in struct_type.fields:
                return_type = struct_type.fields[get_attr.attr]
                index = list(struct_type.fields.keys()).index(get_attr.attr)
            else:
                msg = DefinitionError.field_not_found(get_attr.attr, get_attr.pos, struct_type)
                MessageHandler.handle_message(msg)
                return_type = ErroredTypeSymbol(get_attr.pos)
                index = None
        else:
            struct_type = None
            index = None

        self.symbols.expr(get_attr, set_to=SymbolData.ExprData(return_type, is_lval=obj_is_lval))
        self.symbols.get_attr(get_attr, set_to=SymbolData.GetAttrData(struct_type, index))

    def visit_int(self, num: IntIR):
        # TODO Number size checking and handle the INT_MAX vs INT_MIN problem with unary - in front of a literal
        self.symbols.expr(num, SymbolData.ExprData(self.builtins.general().sint[32], False))

    def visit_ann(self, ann: AnnotationIR):
        self.visit_type(ann.type)

    def visit_get_type(self, type: GetTypeIR):
        try:
            resolved_type = self.current_namespace.lookup_type(type.name)
        except FailedLookupError as err:
            msg = DefinitionError.name_undefined(type, err.failed_name)
            MessageHandler.handle_message(msg)
            resolved_type = ErroredTypeSymbol(type.pos)
        self.symbols.type(type, SymbolData.TypeData(resolved_type))
