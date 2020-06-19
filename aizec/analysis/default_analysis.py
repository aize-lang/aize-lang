from __future__ import annotations

from aizec.common import *
from aizec.aize_common import AizeMessage, Reporter, MessageHandler, ErrorLevel, Position

from aizec.ir import IR, Extension
from aizec.ir.nodes import *
from aizec.ir_pass import IRTreePass, IRPassSequence, PassesRegister, PassAlias

from .symbol_data import SymbolData
from .symbols import *


# region Errors
# TODO Errors could be unified into one class with multiple constructors
class DefinitionError(AizeMessage):
    def __init__(self, msg: str, pos: Position, notes: List[AizeMessage]):
        super().__init__(ErrorLevel.ERROR)
        self.msg = msg
        self.pos = pos

        self.notes = notes

    @classmethod
    def name_existing(cls, pos: Position, existing: Symbol = None):
        if existing:
            notes = [DefinitionNote.from_pos(existing.position, "Previously declared here")]
        else:
            notes = []
        error = cls(f"Name '{existing.name}' already declared in this scope", pos, notes)
        return error

    @classmethod
    def name_undefined(cls, pos: Position, name: str):
        error = cls.from_pos(pos, f"Name '{name}' could not be found")
        return error

    @classmethod
    def field_not_found(cls, field_name: str, accessor: Position, struct_type: StructTypeSymbol):
        note = DefinitionNote.from_pos(struct_type.position, f"{struct_type} defined here")
        error = cls(f"Field '{field_name}' not found on {struct_type}", accessor, [])
        return error

    @classmethod
    def field_repeated(cls, repeat: Position, original: Position, name: str):
        note = DefinitionNote.from_pos(original, "Previously declared here")
        error = cls.from_pos(repeat, f"Field name '{name}' repeated", note)
        return error

    @classmethod
    def no_such_intrinsic(cls, intrinsic: Position, name: str):
        error = cls.from_pos(intrinsic, f"No intrinsic with name '{name}'")
        return error

    @classmethod
    def from_pos(cls, pos: Position, msg: str, note: AizeMessage = None):
        return cls(msg, pos, [note] if note else [])

    @classmethod
    def from_node(cls, node: TextIR, msg: str, note: AizeMessage = None):
        return cls.from_pos(node.pos, msg, note)

    def display(self, reporter: Reporter):
        reporter.positioned_error("Name Resolution Error", self.msg, self.pos)
        for note in self.notes:
            reporter.separate()
            with reporter.indent():
                note.display(reporter)


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
    def expected_type(cls, expected: TypeSymbol, got: TypeSymbol, where: Position, declaration: Position = None):
        if declaration:
            notes = [DefinitionNote(f"Expected type declared here", declaration)]
        else:
            notes = []
        error = cls(f"Expected type {expected}, got type {got}", where, notes)
        return error

    @classmethod
    def expected_lval(cls, pos: Position):
        error = cls(f"Expected a place to store to, such as a variable or a field", pos)
        return error

    def display(self, reporter: Reporter):
        reporter.positioned_error("Type Checking Error", self.msg, self.pos)
        for note in self.notes:
            reporter.separate()
            with reporter.indent():
                note.display(reporter)


class FlowError(AizeMessage):
    def __init__(self, msg: str, pos: Position):
        super().__init__(ErrorLevel.ERROR)
        self.msg = msg
        self.pos = pos

    def display(self, reporter: Reporter):
        reporter.positioned_error("Control Flow Error", self.msg, self.pos)


class MalformedASTError(AizeMessage):
    def __init__(self, msg: str, pos: Position):
        super().__init__(ErrorLevel.ERROR)
        self.msg = msg
        self.pos = pos

    def display(self, reporter: Reporter):
        reporter.positioned_error("AST Conversion Error", self.msg, self.pos)
# endregion


DefaultPasses = IRPassSequence("DefaultPasses")
PassesRegister.register(DefaultPasses)


class LiteralData(Extension):
    class BuiltinData:
        def __init__(self,
                     uint: Dict[int, TypeSymbol],
                     sint: Dict[int, TypeSymbol]):
            self.uint = uint
            self.sint = sint

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

    def set_attr(self, node: SetAttrIR, set_to=None):
        raise NotImplementedError()

    def intrinsic(self, node: IntrinsicIR, set_to=None):
        raise NotImplementedError()

    def get_static_attr_expr(self, node: GetStaticAttrExprIR, set_to=None):
        raise NotImplementedError()

    def namespace(self, node: NamespaceIR, set_to=None):
        raise NotImplementedError()

    def type(self, node: TypeIR, set_to=None):
        raise NotImplementedError()


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
        builtin_namespace = NamespaceSymbol("program", Position.new_none())
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

        self.builtins.general(set_to=LiteralData.BuiltinData({1: uint1, 8: uint8, 32: uint32, 64: uint64},
                                                             {8: int8, 32: int32, 64: int64}))

        with self.enter_namespace(builtin_namespace):
            for source in program.sources:
                self.visit_source(source)

    def visit_source(self, source: SourceIR):
        global_namespace = NamespaceSymbol(f"source {source.source_name}", Position.new_source(source.source_name))
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

    def visit_import(self, imp: ImportIR):
        source = imp.source_ir
        namespace = self.symbols.source(source).globals

        raw_name = imp.path.with_suffix("").name
        fixed_name = raw_name.replace(" ", "_")
        if not fixed_name.isidentifier():
            # TODO
            raise Exception(raw_name)

        try:
            self.current_namespace.define_namespace(namespace, as_name=fixed_name, is_parent=False)
        except DuplicateSymbolError as err:
            msg = DefinitionError.name_existing(imp.pos, err.old_symbol)
            MessageHandler.handle_message(msg)

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
            msg = DefinitionError.name_undefined(type.pos, err.failed_name)
            MessageHandler.handle_message(msg)
            resolved_type = ErroredTypeSymbol(type.pos)
        self.symbols.type(type, SymbolData.TypeData(resolved_type))


@PassesRegister.register(to_sequences=[DefaultPasses])
class DeclareFunctions(IRSymbolsPass):
    def __init__(self, ir: IR):
        super().__init__(ir)

        self.builtins: LiteralData = self.get_ext(LiteralData)
        self.symbols: SymbolData = self.get_ext(SymbolData)

    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return {InitSymbols, DeclareTypes}

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
            msg = DefinitionError.name_existing(func.pos, err.old_symbol)
            MessageHandler.handle_message(msg)

        func_namespace = NamespaceSymbol(f"function {func.name}", func.pos)
        self.current_namespace.define_namespace(func_namespace, visible=False)

        attrs = [attr.name for attr in func.attrs]

        self.symbols.function(func, set_to=SymbolData.FunctionData(func_value, func_namespace, attrs))
        self.symbols.decl(func, set_to=SymbolData.DeclData(func, func_value, func_type))

    def visit_param(self, param: ParamIR):
        self.visit_type(param.type)
        symbol = VariableSymbol(param.name, param, self.symbols.type(param.type).resolved_type, param.pos)
        self.symbols.param(param, set_to=SymbolData.ParamData(symbol))

    def visit_get_type(self, type: GetTypeIR):
        try:
            resolved_type = self.current_namespace.lookup_type(type.name)
        except FailedLookupError as err:
            msg = DefinitionError.name_undefined(type.pos, err.failed_name)
            MessageHandler.handle_message(msg)
            resolved_type = ErroredTypeSymbol(type.pos)
        self.symbols.type(type, set_to=SymbolData.TypeData(resolved_type))


@PassesRegister.register(to_sequences=[DefaultPasses])
class ResolveSymbols(IRSymbolsPass):
    def __init__(self, ir: IR):
        super().__init__(ir)
        self._current_func: Optional[FunctionIR] = None
        self._current_func_type: Optional[FunctionTypeSymbol] = None

        self.builtins: LiteralData = self.get_ext(LiteralData)
        self.symbols: SymbolData = self.get_ext(SymbolData)

    # region Pass Info
    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return {InitSymbols, DeclareTypes, DeclareFunctions}

    @classmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        return {LiteralData, SymbolData}
    # endregion

    # region Current Function Utils
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
    # endregion

    # region Type Checking Utils
    def lookup_type(self, name: str, pos: Position, in_namespace: NamespaceSymbol = None) -> TypeSymbol:
        if in_namespace is None:
            in_namespace = self.current_namespace
        try:
            resolved_type = in_namespace.lookup_type(name)
        except FailedLookupError as err:
            msg = DefinitionError.name_undefined(pos, err.failed_name)
            MessageHandler.handle_message(msg)
            resolved_type = ErroredTypeSymbol(pos)
        return resolved_type

    def lookup_value(self, name: str, node: TextIR, in_namespace: NamespaceSymbol = None) -> VariableSymbol:
        if in_namespace is None:
            in_namespace = self.current_namespace
        try:
            resolved_value = in_namespace.lookup_value(name)
        except FailedLookupError as err:
            msg = DefinitionError.name_undefined(node.pos, err.failed_name)
            MessageHandler.handle_message(msg)
            resolved_value = ErroredVariableSymbol(node, node.pos)
        return resolved_value

    def lookup_namespace(self, name: str, node: TextIR, in_namespace: NamespaceSymbol = None) -> NamespaceSymbol:
        if in_namespace is None:
            in_namespace = self.current_namespace
        try:
            resolved_namespace = in_namespace.lookup_namespace(name)
        except FailedLookupError as err:
            msg = DefinitionError.name_undefined(node.pos, err.failed_name)
            MessageHandler.handle_message(msg)
            resolved_namespace = ErroredNamespaceSymbol(node.pos)
        return resolved_namespace

    def define_value(self, symbol: VariableSymbol, in_namespace: NamespaceSymbol = None):
        if in_namespace is None:
            in_namespace = self.current_namespace
        try:
            in_namespace.define_value(symbol)
        except DuplicateSymbolError as err:
            msg = DefinitionError.name_existing(symbol.position)
            MessageHandler.handle_message(msg)

    def check_argument_count(self, arguments: List[ExprIR], expected_count: int, pos: Position) -> bool:
        got_count = len(arguments)
        if got_count > expected_count:
            excess = arguments[got_count - expected_count]
            msg = TypeCheckingError.too_many_arguments(expected_count, got_count, excess.pos)
            MessageHandler.handle_message(msg)
            return False
        elif got_count < expected_count:
            msg = TypeCheckingError.too_few_arguments(expected_count, got_count, pos)
            MessageHandler.handle_message(msg)
            return False
        else:
            return True

    def check_arguments(self, arguments: List[ExprIR], params: List[TypeSymbol], pos: Position):
        for arg, param in zip(arguments, params):
            arg_type = self.symbols.expr(arg).return_type
            if param.is_super_of(arg_type):
                pass
            else:
                msg = TypeCheckingError.expected_type(param, arg_type, arg.pos)
                MessageHandler.handle_message(msg)

        self.check_argument_count(arguments, len(params), pos)

    def check_type(self, expr: ExprIR, expected: TypeSymbol, decl: Optional[Position], node: TextIR) -> Optional[TypeSymbol]:
        got_type = self.symbols.expr(expr).return_type
        for type in [expected, got_type]:
            if isinstance(type, ErroredTypeSymbol):
                return type
        else:
            if expected.is_super_of(got_type):
                return None
            else:
                msg = TypeCheckingError.expected_type(expected, got_type, expr.pos, decl)
                MessageHandler.handle_message(msg)
                return ErroredTypeSymbol(node.pos)

    def check_type_cls(self, exprs: List[Union[ExprIR, TypeIR]], cls: Type[TypeSymbol], place: Position, err_msg: str) -> Optional[TypeSymbol]:
        types = [self.symbols.expr(expr).return_type
                 if isinstance(expr, ExprIR) else
                 self.symbols.type(expr).resolved_type
                 for expr in exprs]
        positions = [expr.pos for expr in exprs]
        for type in types:
            if isinstance(type, ErroredTypeSymbol):
                return type

        failed: bool = False
        for pos, type in zip(positions, types):
            if not isinstance(type, cls):
                msg = TypeCheckingError(f"{err_msg}, got {type}", pos)
                MessageHandler.handle_message(msg)
                failed = True
        if failed:
            return ErroredTypeSymbol(place)
        else:
            return None

    def check_ints(self, nodes: List[ExprIR], node: ExprIR, same_signs: bool = True) -> Optional[TypeSymbol]:
        # noinspection PyTypeChecker
        node_name = {CompareIR: "Comparison", ArithmeticIR: "Arithmetic", NegateIR: "Negate"}.get(type(node), "Expression")
        if errored_type := self.check_type_cls(nodes, IntTypeSymbol, node.pos,
                                               f"{node_name} expected {'an integer' if len(nodes) == 1 else 'integers'}"):
            return errored_type
        else:
            if same_signs:
                node_types: List[IntTypeSymbol] = [cast(IntTypeSymbol, self.symbols.expr(node).return_type) for node in nodes]
                if node_types.count(node_types[0]) == len(node_types):
                    return None
                else:
                    msg = TypeCheckingError(f"Signed and Unsigned Integers cannot be mixed in {node_name}", node.pos, [])
                    MessageHandler.handle_message(msg)
                    return ErroredTypeSymbol(node.pos)
            else:
                return None
    # endregion

    def visit_program(self, program: ProgramIR):
        with self.enter_namespace(self.symbols.program(program).builtins):
            for source in program.sources:
                self.visit_source(source)

    def visit_source(self, source: SourceIR):
        with self.enter_namespace(self.symbols.source(source).globals):
            for top_level in source.top_levels:
                self.visit_top_level(top_level)

    def visit_function(self, func: FunctionIR):
        data = self.symbols.function(func)
        func_type = cast(FunctionTypeSymbol, data.symbol.type)
        func_namespace = data.namespace

        with self.in_function(func, func_type):
            for param in func.params:
                param_symbol = self.symbols.param(param).symbol

                self.define_value(param_symbol, in_namespace=func_namespace)

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

    def visit_if(self, if_: IfStmtIR):
        self.visit_expr(if_.cond)
        self.visit_stmt(if_.else_do)
        self.visit_stmt(if_.then_do)

        boolean = self.builtins.general().uint[1]
        self.check_type(if_.cond, boolean, None, if_)
        is_terminal = self.symbols.stmt(if_.else_do).is_terminal and self.symbols.stmt(if_.then_do).is_terminal
        self.symbols.stmt(if_, set_to=SymbolData.StmtData(is_terminal))

    def visit_while(self, while_: WhileStmtIR):
        self.visit_expr(while_.cond)
        self.visit_stmt(while_.while_do)

        boolean = self.builtins.general().uint[1]
        self.check_type(while_.cond, boolean, None, while_)
        is_terminal = self.symbols.stmt(while_.while_do).is_terminal
        self.symbols.stmt(while_, set_to=SymbolData.StmtData(is_terminal))

    def visit_expr_stmt(self, stmt: ExprStmtIR):
        self.visit_expr(stmt.expr)
        self.symbols.stmt(stmt, set_to=SymbolData.StmtData(is_terminal=False))

    def visit_var_decl(self, decl: VarDeclIR):
        self.visit_ann(decl.ann)
        var_type = self.symbols.type(decl.ann.type).resolved_type

        self.visit_expr(decl.value)
        value_type = self.symbols.expr(decl.value).return_type

        self.check_type(decl.value, var_type, decl.ann.pos, decl)

        symbol = VariableSymbol(decl.name, decl, var_type, decl.pos)
        self.define_value(symbol)

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
        self.check_type(ret.expr, expected, self.current_func.ret.pos, ret)
        self.symbols.stmt(ret, set_to=SymbolData.StmtData(True))

    def visit_compare(self, cmp: CompareIR):
        self.visit_expr(cmp.left)
        self.visit_expr(cmp.right)
        left = self.symbols.expr(cmp.left).return_type
        right = self.symbols.expr(cmp.right).return_type

        if errored_type := self.check_ints([cmp.left, cmp.right], cmp):
            return_type = errored_type
            is_signed = True
        else:
            left = cast(IntTypeSymbol, self.symbols.expr(cmp.left).return_type)
            right = cast(IntTypeSymbol, self.symbols.expr(cmp.right).return_type)
            is_signed = left.is_signed
            return_type = self.builtins.general().uint[1]
                
        self.symbols.expr(cmp, SymbolData.ExprData(return_type, False))
        self.symbols.compare(cmp, SymbolData.CompareData(is_signed))

    def visit_arithmetic(self, arith: ArithmeticIR):
        self.visit_expr(arith.left)
        self.visit_expr(arith.right)

        if errored_type := self.check_ints([arith.left, arith.right], arith):
            return_type = errored_type
            is_signed = True
        else:
            left = cast(IntTypeSymbol, self.symbols.expr(arith.left).return_type)
            right = cast(IntTypeSymbol, self.symbols.expr(arith.right).return_type)
            is_signed = left.is_signed
            return_type = max(left, right, key=lambda t: t.bit_size)

        self.symbols.expr(arith, SymbolData.ExprData(return_type, False))
        self.symbols.arithmetic(arith, SymbolData.ArithmeticData(is_signed))

    def visit_negate(self, negate: NegateIR):
        self.visit_expr(negate.right)

        if errored_type := self.check_ints([negate.right], negate):
            return_type = errored_type
        else:
            right = cast(IntTypeSymbol, self.symbols.expr(negate.right).return_type)
            return_type = right

        self.symbols.expr(negate, set_to=SymbolData.ExprData(return_type, False))

    def visit_new(self, new: NewIR):
        self.visit_type(new.type)
        for arg in new.arguments:
            self.visit_expr(arg)

        if errored_type := self.check_type_cls([new.type], StructTypeSymbol, new.pos, "New expected a struct"):
            return_type = errored_type
        else:
            return_type = struct_type = cast(StructTypeSymbol, self.symbols.type(new.type).resolved_type)
            self.check_arguments(new.arguments, [field_type for _, field_type in struct_type.fields.items()], new.pos)

        self.symbols.expr(new, set_to=SymbolData.ExprData(return_type, False))

    def visit_call(self, call: CallIR):
        self.visit_expr(call.callee)
        for arg in call.arguments:
            self.visit_expr(arg)

        if errored_type := self.check_type_cls([call.callee], FunctionTypeSymbol, call.pos, "Call expected a function"):
            return_type = errored_type
        else:
            func_type = cast(FunctionTypeSymbol, self.symbols.expr(call.callee).return_type)
            return_type = func_type.ret
            self.check_arguments(call.arguments, func_type.params, call.pos)

        self.symbols.expr(call, SymbolData.ExprData(return_type, False))

    def visit_get_var(self, get_var: GetVarIR):
        variable = self.lookup_value(get_var.var_name, get_var)
        is_function = isinstance(variable.type, FunctionTypeSymbol)
        self.symbols.expr(get_var, SymbolData.ExprData(variable.type, is_lval=not is_function))
        self.symbols.get_var(get_var, set_to=SymbolData.GetVarData(variable, is_function))

    def visit_set_var(self, set_var: SetVarIR):
        self.visit_expr(set_var.value)

        variable = self.lookup_value(set_var.var_name, set_var)
        variable_type = variable.type

        value_type = self.symbols.expr(set_var.value).return_type

        if errored_type := self.check_type(set_var.value, variable_type, variable.position, set_var):
            return_type = errored_type
        else:
            return_type = value_type

        self.symbols.expr(set_var, set_to=SymbolData.ExprData(return_type, True))
        self.symbols.set_var(set_var, set_to=SymbolData.SetVarData(variable))

    def visit_get_attr(self, get_attr: GetAttrIR):
        self.visit_expr(get_attr.obj)
        obj_type = self.symbols.expr(get_attr.obj).return_type
        obj_is_lval = self.symbols.expr(get_attr.obj).is_lval

        return_type: TypeSymbol
        if errored_type := self.check_type_cls([get_attr.obj], StructTypeSymbol, get_attr.pos, "Get Attribute expected a struct"):
            return_type = errored_type
            struct_type = errored_type
            index = None
        else:
            struct_type = cast(StructTypeSymbol, obj_type)
            if get_attr.attr in struct_type.fields:
                return_type = struct_type.fields[get_attr.attr]
                index = list(struct_type.fields.keys()).index(get_attr.attr)
            else:
                msg = DefinitionError.field_not_found(get_attr.attr, get_attr.pos, struct_type)
                MessageHandler.handle_message(msg)
                return_type = ErroredTypeSymbol(get_attr.pos)
                index = None

        self.symbols.expr(get_attr, set_to=SymbolData.ExprData(return_type, is_lval=obj_is_lval))
        self.symbols.get_attr(get_attr, set_to=SymbolData.GetAttrData(struct_type, index))

    def visit_set_attr(self, set_attr: SetAttrIR):
        self.visit_expr(set_attr.obj)
        obj_type = self.symbols.expr(set_attr.obj).return_type
        obj_is_lval = self.symbols.expr(set_attr.obj).is_lval

        self.visit_expr(set_attr.value)
        value_type = self.symbols.expr(set_attr.value).return_type
        value_is_lval = self.symbols.expr(set_attr.value).is_lval

        return_type: TypeSymbol
        if errored_type := self.check_type_cls([set_attr.obj], StructTypeSymbol, set_attr.pos, "Set Attribute expected a struct"):
            return_type = errored_type
            struct_type = None
            index = None
        else:
            struct_type = cast(StructTypeSymbol, obj_type)

            if set_attr.attr in struct_type.fields:
                field_type = struct_type.fields[set_attr.attr]
                field_pos = struct_type.field_pos[set_attr.attr]
                index = list(struct_type.fields.keys()).index(set_attr.attr)

                if errored_type := self.check_type(set_attr.value, field_type, field_pos, set_attr):
                    return_type = errored_type
                else:
                    return_type = value_type
            else:
                msg = DefinitionError.field_not_found(set_attr.attr, set_attr.pos, struct_type)
                MessageHandler.handle_message(msg)
                return_type = ErroredTypeSymbol(set_attr.pos)
                index = None

        if not obj_is_lval:
            msg = TypeCheckingError.expected_lval(set_attr.obj.pos)
            MessageHandler.handle_message(msg)

        self.symbols.expr(set_attr, set_to=SymbolData.ExprData(return_type, is_lval=True))
        self.symbols.set_attr(set_attr, set_to=SymbolData.SetAttrData(struct_type, index))

    def visit_intrinsic(self, intrinsic: IntrinsicIR):
        if intrinsic.name in ('int8', 'int32', 'int64'):
            to_bits = int(intrinsic.name[3:])
            return_type: TypeSymbol

            for arg in intrinsic.args:
                self.visit_expr(arg)

            if self.check_argument_count(intrinsic.args, 1, intrinsic.pos):
                num = intrinsic.args[0]
                if errored_type := self.check_ints([num], intrinsic, same_signs=False):
                    return_type = errored_type
                else:
                    return_type = self.builtins.general().sint[to_bits]
            else:
                return_type = return_type = ErroredTypeSymbol(intrinsic.pos)

            self.symbols.expr(intrinsic, set_to=SymbolData.ExprData(return_type, False))
        else:
            msg = DefinitionError.no_such_intrinsic(intrinsic.pos, intrinsic.name)
            MessageHandler.handle_message(msg)
            self.symbols.expr(intrinsic, set_to=SymbolData.ExprData(ErroredTypeSymbol(intrinsic.pos), False))

    def visit_get_static_attr_expr(self, get_static: GetStaticAttrExprIR):
        self.visit_namespace(get_static.namespace)
        namespace = self.symbols.namespace(get_static.namespace).resolved_namespace
        if isinstance(namespace, ErroredNamespaceSymbol):
            resolved_value = ErroredVariableSymbol(get_static, get_static.pos)
        else:
            resolved_value = self.lookup_value(get_static.attr, get_static, in_namespace=namespace)

        self.symbols.expr(get_static, set_to=SymbolData.ExprData(resolved_value.type, False))
        self.symbols.get_static_attr_expr(get_static, set_to=SymbolData.GetStaticAttrExprData(resolved_value))

    def visit_int(self, num: IntIR):
        # TODO Number size checking and handle the INT_MAX vs INT_MIN problem with unary - in front of a literal
        self.symbols.expr(num, SymbolData.ExprData(self.builtins.general().sint[32], False))

    def visit_ann(self, ann: AnnotationIR):
        self.visit_type(ann.type)

    def visit_get_type(self, type: GetTypeIR):
        resolved_type = self.lookup_type(type.name, type.pos)
        self.symbols.type(type, SymbolData.TypeData(resolved_type))

    def visit_get_namespace(self, namespace: GetNamespaceIR):
        resolved_namespace = self.lookup_namespace(namespace.name, namespace)
        self.symbols.namespace(namespace, set_to=SymbolData.NamespaceData(resolved_namespace))

    def visit_malformed_namespace(self, malformed: MalformedNamespaceIR):
        msg = MalformedASTError(f"Could resolve expression to a namespace", malformed.pos)
        MessageHandler.handle_message(msg)
        self.symbols.namespace(malformed, set_to=SymbolData.NamespaceData(ErroredNamespaceSymbol(malformed.pos)))
