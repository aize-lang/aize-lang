from __future__ import annotations

from abc import ABCMeta

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
    def create_ir(cls, program: ProgramAST) -> ProgramIR:
        return cls(program).visit_program(program)

    def visit_program(self, program: ProgramAST) -> ProgramIR:
        data = ProgramData(UnknownTypeSymbol(Position.new_none()), UnknownTypeSymbol(Position.new_none()))
        return ProgramIR([self.visit_source(source) for source in program.sources], NoNamespaceSymbol(), data)

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


class IRVisitor(ABC):
    @abstractmethod
    def visit_program(self, program: ProgramIR):
        pass

    @abstractmethod
    def visit_source(self, source: SourceIR):
        pass

    def visit_top_level(self, top_level: TopLevelIR):
        if isinstance(top_level, ClassIR):
            return self.visit_class(top_level)
        elif isinstance(top_level, FunctionIR):
            return self.visit_function(top_level)
        else:
            raise TypeError(f"Expected a top-level node, got {top_level}")

    @abstractmethod
    def visit_class(self, cls: ClassIR):
        pass

    @abstractmethod
    def visit_function(self, func: FunctionIR):
        pass

    @abstractmethod
    def visit_field(self, attr: FieldIR):
        pass

    @abstractmethod
    def visit_method_def(self, method: MethodDefIR):
        pass

    @abstractmethod
    def visit_param(self, param: ParamIR):
        pass

    def visit_stmt(self, stmt: StmtIR):
        if isinstance(stmt, ReturnIR):
            return self.visit_return(stmt)
        else:
            raise TypeError(f"Expected a stmt node, got {stmt}")

    @abstractmethod
    def visit_return(self, ret: ReturnIR):
        pass

    def visit_expr(self, expr: ExprIR):
        if isinstance(expr, IntIR):
            return self.visit_int(expr)
        else:
            raise TypeError(f"Expected a expr node, got {expr}")

    @abstractmethod
    def visit_int(self, num: IntIR):
        pass

    @abstractmethod
    def visit_ann(self, ann: AnnotationIR):
        pass

    def visit_type(self, type: TypeIR):
        if isinstance(type, GetTypeIR):
            return self.visit_get_type(type)
        else:
            raise TypeError(f"Expected a type node, got {type}")

    @abstractmethod
    def visit_get_type(self, type: GetTypeIR):
        pass


class PassesRegister:
    _instance_ = None

    def __init__(self):
        self._passes: Dict[str, IRPass] = {}

    @classmethod
    def _instance(cls):
        if cls._instance_ is None:
            cls._instance_ = cls()
        return cls._instance_

    @classmethod
    @overload
    def register(cls, pass_: IRPass) -> IRPass:
        pass

    @classmethod
    @overload
    def register(cls, *, to_sequences: Iterable[str] = None) -> Callable[[IRPass], IRPass]:
        pass

    @classmethod
    def register(cls, pass_: IRPass = None, *, to_sequences: Iterable[str] = None):
        inst = cls._instance()
        if to_sequences is None:
            to_sequences = []
        to_sequences = set(to_sequences)

        def _register(ir_pass: IRPass):
            for seq_name in to_sequences:
                seq = inst.get_pass(seq_name)
                if isinstance(seq, IRPassSequence):
                    seq.add_pass(ir_pass)
                else:
                    raise ValueError(f"{seq_name} not a IRPassSequence")
            inst._passes[ir_pass.name] = ir_pass
            return ir_pass

        if pass_ is None:
            return _register
        else:
            return _register(pass_)

    @classmethod
    def get_pass(cls, name: str) -> IRPass:
        return cls._instance()._passes[name]


class IRPass(ABC):
    def __init__(self, name: str):
        self.name: str = name

    @abstractmethod
    def get_prerequisites(self) -> Set[str]:
        pass

    @abstractmethod
    def apply_pass(self, program: ProgramIR) -> Set[str]:
        pass


# region Metaclass Magic
class IRPassMetaclass(IRPass, ABC, ABCMeta):
    pass


class IRPassClass:
    __metaclass__ = IRPassMetaclass

    name: str

    def __init_subclass__(cls):
        cls.name = cls.get_name()

    @classmethod
    def get_name(cls) -> str:
        return cls.__name__

    @classmethod
    @abstractmethod
    def get_prerequisites(cls) -> Set[str]:
        pass

    @classmethod
    @abstractmethod
    def apply_pass(cls, program: ProgramIR) -> Set[str]:
        pass
# endregion


class IRTreePass(IRVisitor, IRPassClass, ABC):
    def __init__(self, program: ProgramIR):
        self._table = SymbolTable()
        self.data: ProgramData = program.data

    @classmethod
    def apply_pass(cls, program: ProgramIR) -> Set[str]:
        cls(program).visit_program(program)
        MessageHandler.flush_messages()
        return {cls.name}

    def enter_namespace(self, namespace: NamespaceSymbol):
        return self._table.enter(namespace)

    def enter_node(self, node: WithNamespace):
        namespace = node.namespace
        if namespace.namespace is not None:
            if namespace.namespace is not self.current_namespace:
                raise ValueError("When entering a namespace, it must be a child of the current namespace")
        return self._table.enter(node.namespace)

    @property
    def current_namespace(self) -> NamespaceSymbol:
        return self._table.current_namespace

    def visit_program(self, program: ProgramIR):
        with self.enter_node(program):
            for source in program.sources:
                self.visit_source(source)

    def visit_source(self, source: SourceIR):
        with self.enter_node(source):
            for top_level in source.top_levels:
                self.visit_top_level(top_level)

    def visit_function(self, func: FunctionIR):
        pass

    def visit_class(self, cls: ClassIR):
        pass

    def visit_field(self, attr: FieldIR):
        pass

    def visit_method_def(self, method: MethodDefIR):
        pass

    def visit_param(self, param: ParamIR):
        pass

    def visit_return(self, ret: ReturnIR):
        pass

    def visit_int(self, num: IntIR):
        pass

    def visit_ann(self, ann: AnnotationIR):
        pass

    def visit_get_type(self, type: GetTypeIR):
        pass


class IRPassSequence(IRPass):
    def __init__(self, name: str, passes: List[IRPass] = None):
        super().__init__(name)
        self.passes = [] if passes is None else passes

    def get_prerequisites(self) -> Set[str]:
        return self._common

    def add_pass(self, ir_pass: IRPass):
        self.passes.append(ir_pass)
        return ir_pass

    @property
    def _common(self):
        return reduce(set.intersection, (pass_.get_prerequisites() for pass_ in self.passes))

    def apply_pass(self, program: ProgramIR) -> Set[str]:
        run_passes = {self.name}
        for pass_ in self.passes:
            run_passes |= pass_.apply_pass(program)
        return run_passes


DefaultPasses = IRPassSequence("DefaultPasses")
PassesRegister.register(DefaultPasses)


@PassesRegister.register(to_sequences=['DefaultPasses'])
class CreateBuiltins(IRTreePass):
    @classmethod
    def get_prerequisites(cls) -> Set[str]:
        return set()

    def visit_program(self, program: ProgramIR):
        builtin_namespace = NamespaceSymbol("<builtins>", Position.new_none())
        BuiltinsCreator.add_builtins(program.data, builtin_namespace)

        program.namespace = builtin_namespace


@PassesRegister.register(to_sequences=['DefaultPasses'])
class InitSources(IRTreePass):
    @classmethod
    def get_prerequisites(cls) -> Set[str]:
        return {'CreateBuiltins'}

    def visit_source(self, source: SourceIR):
        global_namespace = NamespaceSymbol(f"<{source.source_name} globals>", Position.new_source(source.source_name))
        self.current_namespace.define_namespace(global_namespace, visible=False)

        source.namespace = global_namespace


@PassesRegister.register(to_sequences=['DefaultPasses'])
class DeclareTypes(IRTreePass):
    @classmethod
    def get_prerequisites(cls) -> Set[str]:
        return {'CreateBuiltins', 'InitSources'}


@PassesRegister.register(to_sequences=['DefaultPasses'])
class ResolveTypes(IRTreePass):
    def __init__(self, program: ProgramIR):
        super().__init__(program)
        self._current_func: Optional[FunctionIR] = None
        self._current_func_type: Optional[FunctionTypeSymbol] = None

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

    @classmethod
    def get_prerequisites(cls) -> Set[str]:
        return {'CreateBuiltins', 'InitSources', 'DeclareTypes'}

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
        num.ret_type = self.data.int32

    def visit_get_type(self, type: GetTypeIR):
        try:
            resolved_type = self.current_namespace.lookup_type(type.name)
        except FailedLookupError as err:
            msg = DefinitionError.name_undefined(type, err.failed_name)
            MessageHandler.handle_message(msg)
            resolved_type = ErroredTypeSymbol(type.pos)
        type.resolved_type = resolved_type
