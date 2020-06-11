from __future__ import annotations

from aizec.common import *

from aizec.aize_ir import *

from aizec.aize_error import AizeMessage, Reporter, MessageHandler, ErrorLevel
from aizec.aize_source import *
from aizec.aize_symbols import *


# region Errors
class DefinitionError(AizeMessage):
    def __init__(self, msg: str, pos: Position, note: AizeMessage = None):
        super().__init__(ErrorLevel.ERROR)
        self.msg = msg
        self.pos = pos

        self.note = note

    @classmethod
    def name_existing(cls, node: TextIR, existing: Symbol):
        note = DefinitionNote.from_pos(existing.position, "Previously defined here")
        error = cls.from_node(node, f"Name '{existing.name}' already defined", note)
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
    def __init__(self, source_name: str, pos: Position, msg: str):
        super().__init__(ErrorLevel.NOTE)

        self.source = source_name
        self.pos = pos
        self.msg = msg

    @classmethod
    def from_node(cls, node: TextIR, msg: str):
        return cls.from_pos(node.pos, msg)

    @classmethod
    def from_pos(cls, pos: Position, msg: str):
        return cls(pos.get_source_name(), pos, msg)

    def display(self, reporter: Reporter):
        reporter.positioned_error("Note", self.msg, self.pos)


class TypeCheckingError(AizeMessage):
    def __init__(self, source_name: str, pos: Position, msg: str, note: AizeMessage = None):
        super().__init__(ErrorLevel.ERROR)
        self.source = source_name
        self.pos = pos
        self.msg = msg

        self.note = note

    @classmethod
    def from_nodes(cls, offender: TextIR, definition: TextIR, expected: TypeSymbol, got: TypeSymbol):
        note = DefinitionNote.from_pos(definition.pos, "Declared here")
        error = cls(offender.pos.get_source_name(), offender.pos, f"Expected type {expected}, got type {got}", note)
        return error

    @classmethod
    def function_callee(cls, callee: TextIR, got: TypeSymbol):
        error = cls(callee.pos.get_source_name(), callee.pos, f"Expected a function to call, got {got}")
        return error

    def display(self, reporter: Reporter):
        reporter.positioned_error("Type Checking Error", self.msg, self.pos)
        if self.note is not None:
            reporter.separate()
            with reporter.indent():
                self.note.display(reporter)
# endregion


DefaultPasses = IRPassSequence("DefaultPasses")
PassesRegister.register(DefaultPasses)


class LiteralData(Extension):
    class BuiltinData:
        def __init__(self, int32: TypeSymbol, puts: VariableSymbol):
            self.int32 = int32
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

    def expr(self, node: ExprIR, set_to=None):
        raise NotImplementedError()

    def get_var(self, node: GetVarIR, set_to=None):
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

    class ExprData:
        def __init__(self, return_type: TypeSymbol):
            self.return_type: TypeSymbol = return_type

    def expr(self, node: ExprIR, set_to: ExprData = None) -> ExprData:
        return super().expr(node, set_to)

    class GetVarData:
        def __init__(self, symbol: VariableSymbol):
            self.symbol = symbol

    def get_var(self, node: GetVarIR, set_to: GetVarData = None) -> GetVarData:
        return super().get_var(node, set_to)

    class TypeData:
        def __init__(self, resolved_type: TypeSymbol):
            self.resolved_type: TypeSymbol = resolved_type

    def type(self, node: TypeIR, set_to: TypeData = None) -> TypeData:
        return super().type(node, set_to)


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

        int32 = IntTypeSymbol("int", 32, Position.new_builtin("int"))
        builtin_namespace.define_type(int32)

        puts_type = FunctionTypeSymbol([int32], int32, Position.new_builtin("puts"))
        puts = VariableSymbol("puts", puts_type, Position.new_builtin("puts"))
        builtin_namespace.define_value(puts)

        self.builtins.general(set_to=LiteralData.BuiltinData(int32, puts))

        with self.enter_namespace(builtin_namespace):
            for source in program.sources:
                self.visit_source(source)

    def visit_source(self, source: SourceIR):
        global_namespace = NamespaceSymbol(f"<{source.source_name} globals>", Position.new_source(source.source_name))
        self.current_namespace.define_namespace(global_namespace, visible=False)
        self.symbols.source(source, set_to=SymbolData.SourceData(global_namespace))


@PassesRegister.register(to_sequences=[DefaultPasses])
class DeclareTypes(IRSymbolsPass):
    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return {InitSymbols}

    @classmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        return {LiteralData, SymbolData}


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

        func_value = VariableSymbol(func.name, func_type, func.pos)
        try:
            self.current_namespace.define_value(func_value)
        except DuplicateSymbolError as err:
            msg = DefinitionError.name_existing(func, err.old_symbol)
            MessageHandler.handle_message(msg)

        func_namespace = NamespaceSymbol(f"<{func.name} body>", func.pos)
        self.current_namespace.define_namespace(func_namespace, visible=False)
        self.symbols.function(func, set_to=SymbolData.FunctionData(func_value, func_namespace))

        with self.in_function(func, func_type):
            for param in func.params:
                try:
                    func_namespace.define_value(self.symbols.param(param).symbol)
                except DuplicateSymbolError as err:
                    msg = DefinitionError.param_repeated(func, param, param.name)
                    MessageHandler.handle_message(msg)

        with self.in_function(func, func_type):
            for stmt in func.body:
                self.visit_stmt(stmt)

    def visit_param(self, param: ParamIR):
        self.visit_type(param.type)
        symbol = VariableSymbol(param.name, self.symbols.type(param.type).resolved_type, param.pos)
        self.symbols.param(param, set_to=SymbolData.ParamData(symbol))

    def visit_return(self, ret: ReturnIR):
        self.visit_expr(ret.expr)
        expected = self.current_func_type.ret
        got = self.symbols.expr(ret.expr).return_type
        if expected.is_super_of(got):
            return
        elif isinstance(got, ErroredTypeSymbol):
            return
        else:
            msg = TypeCheckingError.from_nodes(ret, self.current_func, expected, got)
            MessageHandler.handle_message(msg)

    def visit_call(self, call: CallIR):
        self.visit_expr(call.callee)
        for arg in call.arguments:
            self.visit_expr(arg)
        callee_type = self.symbols.expr(call.callee).return_type
        arg_types = [self.symbols.expr(arg).return_type for arg in call.arguments]

        # TODO argument checking, maybe when zip-strict is a thing

        if isinstance(callee_type, FunctionTypeSymbol):
            return_type = callee_type.ret
        elif isinstance(callee_type, ErroredTypeSymbol):
            return_type = callee_type
        else:
            msg = TypeCheckingError.function_callee(call.callee, callee_type)
            MessageHandler.handle_message(msg)
            return_type = ErroredTypeSymbol(call.pos)

        self.symbols.expr(call, SymbolData.ExprData(return_type))

    def visit_get_var(self, get_var: GetVarIR):
        try:
            value = self.current_namespace.lookup_value(get_var.var_name)
        except FailedLookupError:
            msg = DefinitionError.name_undefined(get_var, get_var.var_name)
            MessageHandler.handle_message(msg)
            value = ErroredVariableSymbol(get_var.pos)
        self.symbols.expr(get_var, SymbolData.ExprData(value.type))
        self.symbols.get_var(get_var, SymbolData.GetVarData(value))

    def visit_int(self, num: IntIR):
        # TODO Number size checking and handle the INT_MAX vs INT_MIN problem with unary - in front of a literal
        self.symbols.expr(num, SymbolData.ExprData(self.builtins.general().int32))

    def visit_get_type(self, type: GetTypeIR):
        try:
            resolved_type = self.current_namespace.lookup_type(type.name)
        except FailedLookupError as err:
            msg = DefinitionError.name_undefined(type, err.failed_name)
            MessageHandler.handle_message(msg)
            resolved_type = ErroredTypeSymbol(type.pos)
        self.symbols.type(type, SymbolData.TypeData(resolved_type))
