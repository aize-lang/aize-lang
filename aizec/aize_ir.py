from __future__ import annotations

from abc import ABCMeta

from aizec.common import *

from aizec.aize_ast import *
from aizec.aize_source import *


__all__ = [
    'IR',

    'Extension',

    'PassAlias',
    'PassesRegister', 'PassScheduler',
    'IRTreePass', 'IRPassSequence',

    'NodeIR', 'TextIR',
    'ProgramIR', 'SourceIR',
    'TopLevelIR', 'FunctionIR', 'ClassIR',
    'FieldIR', 'MethodDeclIR', 'MethodDefIR',
    'ParamIR',
    'StmtIR','ReturnIR',
    'ExprIR', 'CallIR', 'IntIR', 'GetVarIR',
    'AnnotationIR',
    'TypeIR', 'GetTypeIR', 'MalformedTypeIR',
]


T = TypeVar('T')


class IR:
    def __init__(self, program: ProgramIR):
        self.program = program
        self.extensions: Dict[Type[Extension], Extension] = {}
        self.ran_passes: Set[PassAlias] = set()

    @classmethod
    def from_ast(cls, program: ProgramAST) -> IR:
        return cls(cls.CreateIR(program).visit_program(program))

    # region IR Creator
    class CreateIR(ASTVisitor):
        def visit_program(self, program: ProgramAST) -> ProgramIR:
            return ProgramIR([self.visit_source(source) for source in program.sources])

        def visit_source(self, source: SourceAST):
            return SourceIR([self.visit_top_level(top_level) for top_level in source.top_levels], source.source.get_name())

        def visit_function(self, func: FunctionAST):
            ann = self.visit_ann(func.ret)
            return FunctionIR(
                name=func.name,
                params=[self.visit_param(param) for param in func.params],
                ret=ann.type,
                body=[self.visit_stmt(stmt) for stmt in func.body],
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
                pos=param.pos
            )

        def visit_return(self, ret: ReturnStmtAST):
            return ReturnIR(self.visit_expr(ret.value), ret.pos)

        def visit_call(self, call: CallExprAST):
            return CallIR(self.visit_expr(call.left), [self.visit_expr(arg) for arg in call.args], call.pos)

        def visit_get_var(self, get_var: GetVarExprAST):
            return GetVarIR(get_var.var, get_var.pos)

        def visit_int(self, num: IntLiteralAST):
            return IntIR(num.num, num.pos)

        def visit_ann(self, ann: ExprAST):
            return AnnotationIR(self.visit_type(ann), ann.pos)

        def handle_malformed_type(self, type: ExprAST):
            return MalformedTypeIR(type.pos)

        def visit_get_type(self, type: GetVarExprAST):
            return GetTypeIR(type.var, type.pos)
    # endregion


# region IR Extension
class Extension:
    def __init__(self, _general_data: Any, node_data: Dict[NodeIR, Dict[str, Any]]):
        self._general_data: Any = _general_data
        self._node_data: Dict[NodeIR, Dict[str, Any]] = node_data

    @classmethod
    def new(cls: Type[E]) -> E:
        return cls(None, {})

    @abstractmethod
    def general(self, set_to: T = None) -> Optional[T]:
        if set_to is not None:
            self._general_data = set_to
        return self._general_data

    def _get_data(self, node: NodeIR, type: str, set_to: T) -> T:
        if set_to is not None:
            self._node_data.setdefault(node, {})[type] = set_to
        try:
            return self._node_data[node][type]
        except KeyError:
            raise ValueError(f"The node of type {node.__class__.__qualname__} has not extensions of type {self.__class__.__qualname__} for class {type!r}")

    @abstractmethod
    def program(self, node: ProgramIR, set_to: T = None) -> T:
        return self._get_data(node, 'program', set_to)

    @abstractmethod
    def source(self, node: SourceIR, set_to: T = None) -> T:
        return self._get_data(node, 'source', set_to)

    @abstractmethod
    def function(self, node: FunctionIR, set_to: T = None) -> T:
        return self._get_data(node, 'function', set_to)

    @abstractmethod
    def param(self, node: ParamIR, set_to: T = None) -> T:
        return self._get_data(node, 'param', set_to)

    @abstractmethod
    def expr(self, node: ExprIR, set_to: T = None) -> T:
        return self._get_data(node, 'expr', set_to)

    @abstractmethod
    def get_var(self, node: GetVarIR, set_to: T = None) -> T:
        return self._get_data(node, 'get_var', set_to)

    @abstractmethod
    def type(self, node: TypeIR, set_to: T = None) -> T:
        return self._get_data(node, 'type', set_to)

    def ext(self, node: NodeIR, type: str, set_to: T = None) -> T:
        return self._get_data(node, type, set_to)


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
        elif isinstance(expr, CallIR):
            return self.visit_call(expr)
        elif isinstance(expr, GetVarIR):
            return self.visit_get_var(expr)
        else:
            raise TypeError(f"Expected a expr node, got {expr}")

    @abstractmethod
    def visit_call(self, call: CallIR):
        pass

    @abstractmethod
    def visit_get_var(self, get_var: GetVarIR):
        pass

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
        self.ir = ir

    @classmethod
    def run_pass(cls, ir: IR):
        pass_class = cls(ir)
        pass_class.visit_program(ir.program)

        if pass_class.was_successful():
            ir.ran_passes.add(cls)

    @abstractmethod
    def was_successful(self) -> bool:
        pass

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

    def has_ext(self, ext_type: Type[E]) -> bool:
        return ext_type in self.ir.extensions

    def get_ext(self, ext_type: Type[E]) -> E:
        try:
            return self.ir.extensions[ext_type]
        except KeyError:
            raise ValueError(f"Extension {ext_type} has not been added to the ir yet. Specify that requirement.")

    def visit_program(self, program: ProgramIR):
        pass

    def visit_source(self, source: SourceIR):
        pass

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

    def visit_call(self, call: CallIR):
        pass

    def visit_get_var(self, get_var: GetVarIR):
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
        ir.ran_passes.add(self)


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
    def register(cls, pass_: IRPass = None, *, to_sequences: Iterable[PassAlias] = None):
        inst = cls._instance()
        if to_sequences is None:
            to_sequences = []
        to_sequences = set(to_sequences)

        def _register(ir_pass: IRPass):
            for seq in to_sequences:
                if isinstance(seq, IRPassSequence):
                    seq.add_pass(ir_pass)
                else:
                    raise ValueError(f"{seq.name} not a IRPassSequence")
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
    def __init__(self, ir: IR, scheduled_passes: List[PassAlias]):
        self.ir = ir
        self.scheduled_passes: List[PassAlias] = scheduled_passes

    def schedule(self, ir_pass: PassAlias) -> bool:
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


# region Base Nodes
class NodeIR:
    pass


class TextIR(NodeIR):
    def __init__(self, pos: Position):
        self.pos = pos
# endregion


# region Program Nodes
class ProgramIR(NodeIR):
    def __init__(self, sources: List[SourceIR]):
        self.sources = sources


class SourceIR(NodeIR):
    def __init__(self, top_levels: List[TopLevelIR], source_name: str):
        self.top_levels = top_levels
        self.source_name = source_name
# endregion


# region Top Level Nodes
class TopLevelIR(TextIR):
    pass


class FunctionIR(TopLevelIR):
    def __init__(self, name: str, params: List[ParamIR], ret: TypeIR, body: List[StmtIR], pos: Position):
        super().__init__(pos)
        self.name = name
        self.params = params
        self.ret = ret
        self.body = body


class ClassIR(TopLevelIR):
    def __init__(self, name: str, fields: Dict[str, FieldIR], methods: Dict[str, MethodDefIR], pos: Position):
        super().__init__(pos)
        self.name = name
        self.fields = fields
        self.methods = methods


# region Class Statement Nodes
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
# endregion
# endregion


# region Parameter Node
class ParamIR(TextIR):
    def __init__(self, name: str, type: TypeIR, pos: Position):
        super().__init__(pos)
        self.name = name
        self.type = type
# endregion


# region Statement Nodes
class StmtIR(TextIR):
    pass


class ReturnIR(StmtIR):
    def __init__(self, expr: ExprIR, pos: Position):
        super().__init__(pos)
        self.expr = expr
# endregion


# region Expression Nodes
class ExprIR(TextIR):
    pass


class CallIR(ExprIR):
    def __init__(self, callee: ExprIR, arguments: List[ExprIR], pos: Position):
        super().__init__(pos)
        self.callee = callee
        self.arguments = arguments


class GetVarIR(ExprIR):
    def __init__(self, var_name: str, pos: Position):
        super().__init__(pos)
        self.var_name = var_name


class IntIR(ExprIR):
    def __init__(self, num: int, pos: Position):
        super().__init__(pos)
        self.num = num
# endregion


# region Annotation Node
class AnnotationIR(TextIR):
    def __init__(self, type: TypeIR, pos: Position):
        super().__init__(pos)
        self.type = type
# endregion


# region Type Nodes
class TypeIR(TextIR):
    def __init__(self, pos: Position):
        super().__init__(pos)


class MalformedTypeIR(TypeIR):
    def __init__(self, pos: Position):
        super().__init__(pos)


class GetTypeIR(TypeIR):
    def __init__(self, name: str, pos: Position):
        super().__init__(pos)
        self.name = name
# endregion


# if __name__ == '__main__':
#     __all__ = ['NodeIR', 'WithNamespace', 'ProgramData'] + [child.__name__ for child in all_subclasses(NodeIR)]
#     print(__all__)
