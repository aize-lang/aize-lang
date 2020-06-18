from __future__ import annotations

from aizec.common import *

from .ir_nodes import *


T = TypeVar('T')


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
            raise ValueError(f"The node of type {node.__class__.__qualname__} has no extensions of type {self.__class__.__qualname__} for class {type!r}") from None

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
    def stmt(self, node: StmtIR, set_to: T = None) -> T:
        return self._get_data(node, 'stmt', set_to)

    @abstractmethod
    def expr(self, node: ExprIR, set_to: T = None) -> T:
        return self._get_data(node, 'expr', set_to)

    @abstractmethod
    def compare(self, node: CompareIR, set_to: T = None) -> T:
        return self._get_data(node, 'compare', set_to)

    @abstractmethod
    def arithmetic(self, node: ArithmeticIR, set_to: T = None) -> T:
        return self._get_data(node, 'arithmetic', set_to)

    @abstractmethod
    def get_var(self, node: GetVarIR, set_to: T = None) -> T:
        return self._get_data(node, 'get_var', set_to)

    @abstractmethod
    def set_var(self, node: SetVarIR, set_to: T = None) -> T:
        return self._get_data(node, 'set_var', set_to)

    @abstractmethod
    def get_attr(self, node: GetAttrIR, set_to: T = None) -> T:
        return self._get_data(node, 'get_attr', set_to)

    @abstractmethod
    def set_attr(self, node: SetAttrIR, set_to: T = None) -> T:
        return self._get_data(node, 'set_attr', set_to)

    @abstractmethod
    def intrinsic(self, node: IntrinsicIR, set_to: T = None) -> T:
        return self._get_data(node, 'intrinsic', set_to)

    @abstractmethod
    def get_static_attr_expr(self, node: GetStaticAttrExprIR, set_to: T = None) -> T:
        return self._get_data(node, 'get_static_attr_expr', set_to)

    @abstractmethod
    def type(self, node: TypeIR, set_to: T = None) -> T:
        return self._get_data(node, 'type', set_to)

    @abstractmethod
    def namespace(self, node: NamespaceIR, set_to: T = None) -> T:
        return self._get_data(node, 'namespace', set_to)

    def ext(self, node: NodeIR, type: str, set_to: T = None) -> T:
        return self._get_data(node, type, set_to)


E = TypeVar('E', bound=Extension)
# endregion
