from __future__ import annotations

from aizec.common import *

from aizec.aize_ast import *
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

    def display(self, reporter: Reporter):
        reporter.positioned_error("Type Checking Error", self.msg, self.pos)
        if self.note is not None:
            reporter.separate()
            with reporter.indent():
                self.note.display(reporter)
# endregion


class BuiltinsCreator:
    def __init__(self, namespace: NamespaceSymbol):
        self.namespace = namespace

    def create_pos(self, name: str):
        return Position.new_builtin(name)

    def create_type(self, name: str):
        type_symbol = TypeSymbol(name, self.create_pos(name))
        self.namespace.define_type(type_symbol)
        return type_symbol

    def create_int_type(self, name: str, bit_size: int):
        int_type_symbol = IntTypeSymbol(name, bit_size, self.create_pos(name))
        self.namespace.define_type(int_type_symbol)
        return int_type_symbol

    @classmethod
    def add_builtins(cls, data: ProgramData, namespace: NamespaceSymbol):
        creator = cls(namespace)
        data.int32 = creator.create_int_type("int", bit_size=32)

        # returned instead of an actual type whenever an inconsistency in types occurs
        data.error_placeholder = creator.create_type("<type check error>")


class CreateIR(ASTVisitor):
    @classmethod
    def create_ir(cls, program: ProgramAST) -> IR:
        return IR(cls(program).visit_program(program))

    def visit_program(self, program: ProgramAST) -> ProgramIR:
        data = ProgramData(UnknownTypeSymbol(Position.new_none()))
        return ProgramIR([self.visit_source(source) for source in program.sources], NoNamespaceSymbol())

    def visit_source(self, source: SourceAST):
        return SourceIR([self.visit_top_level(top_level) for top_level in source.top_levels], source.source.get_name(), NoNamespaceSymbol())

    def visit_function(self, func: FunctionAST):
        ann = self.visit_ann(func.ret)
        return FunctionIR(
            name=func.name,
            params=[self.visit_param(param) for param in func.params],
            ret=ann.type,
            body=[self.visit_stmt(stmt) for stmt in func.body],
            symbol=UnknownVariableSymbol(func.pos),
            namespace=NoNamespaceSymbol(),
            pos=func.pos
        )

    def visit_class(self, cls: ClassAST):
        fields = {}
        methods = {}
        for cls_stmt in cls.body:
            if isinstance(cls_stmt, AttrAST):
                fields[cls_stmt.name] = self.visit_attr(cls_stmt)
            elif isinstance(cls_stmt, MethodAST):
                if isinstance(cls_stmt, MethodImplAST):
                    methods[cls_stmt.name] = self.visit_method(cls_stmt)
                else:
                    pass
            else:
                raise Exception()
        return ClassIR(cls.name, fields, methods, cls.pos)

    def visit_attr(self, attr: AttrAST):
        ann = self.visit_ann(attr.annotation)
        return FieldIR(attr.name, ann.type, attr.pos)

    def visit_method_sig(self, method: MethodSigAST):
        pass

    def visit_method_impl(self, method: MethodImplAST):
        ret_ann = self.visit_ann(method.ret)
        return MethodDefIR(
            name=method.name,
            params=[self.visit_param(param) for param in method.params],
            ret=ret_ann.type,
            body=[self.visit_stmt(stmt) for stmt in method.body],
            pos=method.pos
        )

    def visit_param(self, param: ParamAST):
        ann = self.visit_ann(param.annotation)
        return ParamIR(
            name=param.name,
            type=ann.type,
            symbol=VariableSymbol(param.name, UnknownTypeSymbol(param.pos), param.pos),
            pos=param.pos
        )

    def visit_return(self, ret: ReturnStmtAST):
        return ReturnIR(self.visit_expr(ret.value), ret.pos)

    def visit_int(self, num: IntLiteralAST):
        return IntIR(num.num, num.pos)

    def visit_ann(self, ann: ExprAST):
        return AnnotationIR(self.visit_type(ann), ann.pos)

    def handle_malformed_type(self, type: ExprAST):
        return MalformedTypeIR(UnknownTypeSymbol(type.pos), type.pos)

    def visit_get_type(self, type: GetVarExprAST):
        return GetTypeIR(type.var, UnknownTypeSymbol(type.pos), type.pos)


DefaultPasses = IRPassSequence("DefaultPasses")
PassesRegister.register(DefaultPasses)


class ProgramData:
    def __init__(self, int32: TypeSymbol):
        self.int32 = int32


class LiteralData(Extension):
    def general(self, set_to: ProgramData = None) -> ProgramData:
        return super().general(set_to)

    def program(self, node: ProgramIR, set_to: ProgramData = None) -> ProgramData:
        raise NotImplementedError()


@PassesRegister.register(to_sequences=['DefaultPasses'])
class InitNamespace(IRTreePass):
    def __init__(self, ir: IR):
        super().__init__(ir)

        self.builtins: LiteralData = self.add_ext(LiteralData)

    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return set()

    @classmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        return set()

    def visit_program(self, program: ProgramIR):
        builtin_namespace = NamespaceSymbol("<builtins>", Position.new_none())

        int32 = IntTypeSymbol("int", 32, Position.new_builtin("int"))
        builtin_namespace.define_type(int32)

        data = ProgramData(int32)
        self.builtins.general(set_to=data)

        program.namespace = builtin_namespace

        super().visit_program(program)

    def visit_source(self, source: SourceIR):
        global_namespace = NamespaceSymbol(f"<{source.source_name} globals>", Position.new_source(source.source_name))
        self.current_namespace.define_namespace(global_namespace, visible=False)

        source.namespace = global_namespace


@PassesRegister.register(to_sequences=['DefaultPasses'])
class DeclareTypes(IRTreePass):
    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return set()

    @classmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        return set()


@PassesRegister.register(to_sequences=['DefaultPasses'])
class ResolveTypes(IRTreePass):
    def __init__(self, ir: IR):
        super().__init__(ir)
        self._current_func: Optional[FunctionIR] = None
        self._current_func_type: Optional[FunctionTypeSymbol] = None

        self.builtins = self.get_ext(LiteralData)

    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return {InitNamespace}

    @classmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        return {LiteralData}

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
        with self.enter_node(func):
            yield
        self._current_func = old_func
        self._current_func_type = old_type

    def visit_function(self, func: FunctionIR):
        for param in func.params:
            self.visit_param(param)
        self.visit_type(func.ret)
        params = [param.type.resolved_type for param in func.params]
        ret = func.ret.resolved_type
        func_type = FunctionTypeSymbol(params, ret, func.pos)

        func.value = VariableSymbol(func.name, func_type, func.pos)
        try:
            self.current_namespace.define_value(func.value)
        except DuplicateSymbolError as err:
            msg = DefinitionError.name_existing(func, err.old_symbol)
            MessageHandler.handle_message(msg)

        func.namespace = NamespaceSymbol(f"<{func.name} body>", func.pos)
        with self.in_function(func, func_type):
            for param in func.params:
                try:
                    func.namespace.define_value(param.symbol)
                except DuplicateSymbolError as err:
                    msg = DefinitionError.param_repeated(func, param, param.name)
                    MessageHandler.handle_message(msg)

        with self.in_function(func, func_type):
            for stmt in func.body:
                self.visit_stmt(stmt)

    def visit_param(self, param: ParamIR):
        self.visit_type(param.type)
        param.symbol = VariableSymbol(param.name, param.type.resolved_type, param.pos)

    def visit_return(self, ret: ReturnIR):
        self.visit_expr(ret.expr)
        expected = self.current_func_type.ret
        got = ret.expr.ret_type
        if expected.is_super_of(got):
            return
        else:
            msg = TypeCheckingError.from_nodes(ret, self.current_func, expected, got)
            MessageHandler.handle_message(msg)

    def visit_int(self, num: IntIR):
        # TODO Number size checking and handle the INT_MAX vs INT_MIN problem with unary - in front of a literal
        num.ret_type = self.builtins.general().int32

    def visit_get_type(self, type: GetTypeIR):
        try:
            resolved_type = self.current_namespace.lookup_type(type.name)
        except FailedLookupError as err:
            msg = DefinitionError.name_undefined(type, err.failed_name)
            MessageHandler.handle_message(msg)
            resolved_type = ErroredTypeSymbol(type.pos)
        type.resolved_type = resolved_type
