from __future__ import annotations

from abc import ABCMeta

from aizec.common import *

from aizec.aize_source import *
from aizec.aize_symbols import *
from aizec.aize_error import MessageHandler


__all__ = ['NodeIR', 'TopLevelIR', 'AnnotationIR', 'ProgramIR', 'StmtIR', 'ExprIR', 'ReturnIR',
           'MethodDeclIR', 'IntIR', 'FieldIR', 'TypeIR', 'FunctionIR', 'GetTypeIR', 'SourceIR',
           'MethodDefIR', 'ParamIR', 'TextIR', 'ClassIR', 'MalformedTypeIR', 'WithNamespace',
           'IR', 'Extension', 'PassesRegister', 'PassScheduler', 'IRPassSequence', 'IRTreePass', 'PassAlias']


T = TypeVar('T')


class IR:
    def __init__(self, program: ProgramIR):
        self.program = program
        self.extensions: Dict[Type[Extension], Extension] = {}
        self.ran_passes: Set[PassAlias] = set()


# region IR Extension
class Extension:
    def __init__(self, _general_data: Any, node_data: Dict[NodeIR, Any]):
        self._general_data: Any = _general_data
        self._node_data = node_data

    @classmethod
    def new(cls: Type[E]) -> E:
        return cls(None, {})

    @abstractmethod
    def general(self, set_to: T = None) -> Optional[T]:
        if set_to is not None:
            self._general_data = set_to
        return self._general_data

    @abstractmethod
    def program(self, node: ProgramIR, set_to: T = None) -> T:
        if set_to is not None:
            self._node_data[node] = set_to
        return self._node_data[node]


E = TypeVar('E', bound=Extension)
# endregion


# region IR Pass
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


class IRPassInfo(NamedTuple):
    required_passes: Set[str]
    required_extensions: Set[str]
    runs_passes: Set[str]
    adds_extensions: Set[str]


class IRPass(ABC):
    def __init__(self, name: str):
        self.name: str = name

    @abstractmethod
    def can_run(self, ir: IR) -> bool:
        pass

    @abstractmethod
    def run_pass(self, ir: IR):
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
    def can_run(cls, ir: IR) -> bool:
        pass

    @classmethod
    @abstractmethod
    def run_pass(cls, ir: IR):
        pass
# endregion


class IRTreePass(IRVisitor, IRPassClass, ABC):
    def __init__(self, ir: IR):
        self._table = SymbolTable()
        self.ir = ir

    @classmethod
    def run_pass(cls, ir: IR):
        cls(ir).visit_program(ir.program)

        MessageHandler.flush_messages()

        ir.ran_passes.add(cls)

    @classmethod
    def can_run(cls, ir: IR) -> bool:
        if ir.ran_passes.issuperset(cls.get_required_passes()) \
                and set(ir.extensions.keys()).issuperset(cls.get_required_extensions()):
            return True
        else:
            return False

    @classmethod
    @abstractmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        pass

    @classmethod
    @abstractmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        pass

    def add_ext(self, ext_type: Type[E]) -> E:
        ext_type: Type[Extension]
        ext = ext_type.new()
        self.ir.extensions[ext_type] = ext
        return ext

    def get_ext(self, ext_type: Type[E]) -> E:
        try:
            return self.ir.extensions[ext_type]
        except KeyError:
            raise ValueError(f"Extension {ext_type} has not been added to the ir yet. Specify that requirement.")

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
        self.passes: List[IRPass] = [] if passes is None else passes

    def can_run(self, ir: IR) -> bool:
        return any(ir_pass.can_run(ir) for ir_pass in self.passes)

    def add_pass(self, ir_pass: IRPass):
        self.passes.append(ir_pass)
        return ir_pass

    def run_pass(self, ir: IR):
        scheduler = PassScheduler(ir, self.passes.copy())
        scheduler.run_scheduled()


PassAlias = Union[IRPass, Type[IRTreePass]]


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
    def register(cls, pass_: IRPass, *, to_sequences: Iterable[str] = None) -> IRPass:
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


class PassScheduler:
    def __init__(self, ir: IR, scheduled_passes: List[IRPass]):
        self.ir = ir
        self.scheduled_passes: List[IRPass] = scheduled_passes

    def schedule(self, ir_pass: IRPass) -> bool:
        if ir_pass in self.scheduled_passes:
            return False
        else:
            self.scheduled_passes.append(ir_pass)
            return True

    def run_scheduled(self):
        while len(self.scheduled_passes) > 0:
            for i in range(len(self.scheduled_passes)):
                ir_pass = self.scheduled_passes[i]
                if ir_pass.can_run(self.ir):
                    ir_pass.run_pass(self.ir)
                    self.scheduled_passes.pop(i)
                    break
            else:
                raise ValueError("No passes can be run due to their requirements.")
# endregion


# TODO Move Namespace and other Semantic Analysis Extensions actually into Extensions
class NodeIR:
    pass


class WithNamespace(Protocol):
    namespace: NamespaceSymbol


class ProgramIR(NodeIR):
    def __init__(self, sources: List[SourceIR], namespace: NamespaceSymbol):
        self.sources = sources
        self.namespace = namespace


class SourceIR(NodeIR):
    def __init__(self, top_levels: List[TopLevelIR], source_name: str, namespace: NamespaceSymbol):
        self.top_levels = top_levels
        self.source_name = source_name
        self.namespace = namespace


class TextIR(Positioned, NodeIR):
    def __init__(self, pos: Position):
        super().__init__(pos)


class TopLevelIR(TextIR):
    pass


class FunctionIR(TopLevelIR):
    def __init__(self,
                 name: str,
                 params: List[ParamIR], ret: TypeIR,
                 body: List[StmtIR],
                 symbol: VariableSymbol, namespace: NamespaceSymbol,
                 pos: Position):
        super().__init__(pos)
        self.name = name
        self.params = params
        self.ret = ret
        self.body = body

        self.symbol = symbol
        self.namespace = namespace


class ClassIR(TopLevelIR):
    def __init__(self, name: str, fields: Dict[str, FieldIR], methods: Dict[str, MethodDefIR], pos: Position):
        super().__init__(pos)
        self.name = name
        self.fields = fields
        self.methods = methods


class FieldIR(TextIR):
    def __init__(self, name: str, type: TypeIR, pos: Position):
        super().__init__(pos)
        self.name = name
        self.type = type


class MethodDeclIR(TextIR):
    def __init__(self, name: str, params: List[ParamIR], ret: TypeIR, pos: Position):
        super().__init__(pos)
        self.params = params
        self.ret = ret


class MethodDefIR(TextIR):
    def __init__(self, name: str, params: List[ParamIR], ret: TypeIR, body: List[StmtIR], pos: Position):
        super().__init__(pos)
        self.params = params
        self.ret = ret
        self.body = body


class ParamIR(TextIR):
    def __init__(self, name: str, type: TypeIR, symbol: VariableSymbol, pos: Position):
        super().__init__(pos)
        self.name = name
        self.type = type
        self.symbol = symbol


class StmtIR(TextIR):
    pass


class ReturnIR(StmtIR):
    def __init__(self, expr: ExprIR, pos: Position):
        super().__init__(pos)
        self.expr = expr


class ExprIR(TextIR):
    def __init__(self, ret_type: TypeSymbol, pos: Position):
        super().__init__(pos)
        self.ret_type: TypeSymbol = ret_type


class IntIR(ExprIR):
    def __init__(self, num: int, pos: Position):
        super().__init__(UnknownTypeSymbol(pos), pos)
        self.num = num


class AnnotationIR(TextIR):
    def __init__(self, type: TypeIR, pos: Position):
        super().__init__(pos)
        self.type = type


class TypeIR(TextIR):
    def __init__(self, resolved_type: TypeSymbol, pos: Position):
        super().__init__(pos)
        self.resolved_type = resolved_type


class MalformedTypeIR(TypeIR):
    def __init__(self, resolved_type: TypeSymbol, pos: Position):
        super().__init__(resolved_type, pos)


class GetTypeIR(TypeIR):
    def __init__(self, name: str, resolved_type: TypeSymbol, pos: Position):
        super().__init__(resolved_type, pos)
        self.name = name


# if __name__ == '__main__':
#     __all__ = ['NodeIR', 'WithNamespace', 'ProgramData'] + [child.__name__ for child in all_subclasses(NodeIR)]
#     print(__all__)
