from __future__ import annotations

from aizec.common import *

if __name__ != '__main__':
    from .nodes import *


T = TypeVar('T')


class Extension:
    def __init__(self, _general_data: Any, node_data: Dict[NodeIR, Dict[str, Any]]):
        self._general_data: Any = _general_data
        self._node_data: Dict[NodeIR, Dict[str, Any]] = node_data

    @classmethod
    def create(cls: Type[E]) -> E:
        return cls(None, {})

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

    def text(self, node: TextIR, set_to: T = None) -> T:
        return self._get_data(node, 'text', set_to)

    def program(self, node: ProgramIR, set_to: T = None) -> T:
        return self._get_data(node, 'program', set_to)

    def source(self, node: SourceIR, set_to: T = None) -> T:
        return self._get_data(node, 'source', set_to)

    def top_level(self, node: TopLevelIR, set_to: T = None) -> T:
        return self._get_data(node, 'top_level', set_to)

    def import_(self, node: ImportIR, set_to: T = None) -> T:
        return self._get_data(node, 'import_', set_to)

    def function(self, node: FunctionIR, set_to: T = None) -> T:
        return self._get_data(node, 'function', set_to)

    def struct(self, node: StructIR, set_to: T = None) -> T:
        return self._get_data(node, 'struct', set_to)

    def union(self, node: UnionIR, set_to: T = None) -> T:
        return self._get_data(node, 'union', set_to)

    def variant(self, node: VariantIR, set_to: T = None) -> T:
        return self._get_data(node, 'variant', set_to)

    def agg_func(self, node: AggFuncIR, set_to: T = None) -> T:
        return self._get_data(node, 'agg_func', set_to)

    def agg_field(self, node: AggFieldIR, set_to: T = None) -> T:
        return self._get_data(node, 'agg_field', set_to)

    def param(self, node: ParamIR, set_to: T = None) -> T:
        return self._get_data(node, 'param', set_to)

    def func_attr(self, node: FuncAttrIR, set_to: T = None) -> T:
        return self._get_data(node, 'func_attr', set_to)

    def stmt(self, node: StmtIR, set_to: T = None) -> T:
        return self._get_data(node, 'stmt', set_to)

    def if_stmt(self, node: IfStmtIR, set_to: T = None) -> T:
        return self._get_data(node, 'if_stmt', set_to)

    def while_stmt(self, node: WhileStmtIR, set_to: T = None) -> T:
        return self._get_data(node, 'while_stmt', set_to)

    def var_decl(self, node: VarDeclIR, set_to: T = None) -> T:
        return self._get_data(node, 'var_decl', set_to)

    def block(self, node: BlockIR, set_to: T = None) -> T:
        return self._get_data(node, 'block', set_to)

    def return_(self, node: ReturnIR, set_to: T = None) -> T:
        return self._get_data(node, 'return_', set_to)

    def expr_stmt(self, node: ExprStmtIR, set_to: T = None) -> T:
        return self._get_data(node, 'expr_stmt', set_to)

    def expr(self, node: ExprIR, set_to: T = None) -> T:
        return self._get_data(node, 'expr', set_to)

    def is_(self, node: IsIR, set_to: T = None) -> T:
        return self._get_data(node, 'is_', set_to)

    def compare(self, node: CompareIR, set_to: T = None) -> T:
        return self._get_data(node, 'compare', set_to)

    def arithmetic(self, node: ArithmeticIR, set_to: T = None) -> T:
        return self._get_data(node, 'arithmetic', set_to)

    def negate(self, node: NegateIR, set_to: T = None) -> T:
        return self._get_data(node, 'negate', set_to)

    def tuple(self, node: TupleIR, set_to: T = None) -> T:
        return self._get_data(node, 'tuple', set_to)

    def new(self, node: NewIR, set_to: T = None) -> T:
        return self._get_data(node, 'new', set_to)

    def call(self, node: CallIR, set_to: T = None) -> T:
        return self._get_data(node, 'call', set_to)

    def method_call(self, node: MethodCallIR, set_to: T = None) -> T:
        return self._get_data(node, 'method_call', set_to)

    def get_var(self, node: GetVarIR, set_to: T = None) -> T:
        return self._get_data(node, 'get_var', set_to)

    def set_var(self, node: SetVarIR, set_to: T = None) -> T:
        return self._get_data(node, 'set_var', set_to)

    def get_attr(self, node: GetAttrIR, set_to: T = None) -> T:
        return self._get_data(node, 'get_attr', set_to)

    def set_attr(self, node: SetAttrIR, set_to: T = None) -> T:
        return self._get_data(node, 'set_attr', set_to)

    def intrinsic(self, node: IntrinsicIR, set_to: T = None) -> T:
        return self._get_data(node, 'intrinsic', set_to)

    def get_static_attr_expr(self, node: GetStaticAttrExprIR, set_to: T = None) -> T:
        return self._get_data(node, 'get_static_attr_expr', set_to)

    def cast_int(self, node: CastIntIR, set_to: T = None) -> T:
        return self._get_data(node, 'cast_int', set_to)

    def cast_union(self, node: CastUnionIR, set_to: T = None) -> T:
        return self._get_data(node, 'cast_union', set_to)

    def lambda_(self, node: LambdaIR, set_to: T = None) -> T:
        return self._get_data(node, 'lambda_', set_to)

    def int(self, node: IntIR, set_to: T = None) -> T:
        return self._get_data(node, 'int', set_to)

    def annotation(self, node: AnnotationIR, set_to: T = None) -> T:
        return self._get_data(node, 'annotation', set_to)

    def type(self, node: TypeIR, set_to: T = None) -> T:
        return self._get_data(node, 'type', set_to)

    def generated_type(self, node: GeneratedTypeIR, set_to: T = None) -> T:
        return self._get_data(node, 'generated_type', set_to)

    def get_type(self, node: GetTypeIR, set_to: T = None) -> T:
        return self._get_data(node, 'get_type', set_to)

    def func_type(self, node: FuncTypeIR, set_to: T = None) -> T:
        return self._get_data(node, 'func_type', set_to)

    def tuple_type(self, node: TupleTypeIR, set_to: T = None) -> T:
        return self._get_data(node, 'tuple_type', set_to)

    def no_type(self, node: NoTypeIR, set_to: T = None) -> T:
        return self._get_data(node, 'no_type', set_to)

    def malformed_type(self, node: MalformedTypeIR, set_to: T = None) -> T:
        return self._get_data(node, 'malformed_type', set_to)

    def namespace(self, node: NamespaceIR, set_to: T = None) -> T:
        return self._get_data(node, 'namespace', set_to)

    def get_namespace(self, node: GetNamespaceIR, set_to: T = None) -> T:
        return self._get_data(node, 'get_namespace', set_to)

    def malformed_namespace(self, node: MalformedNamespaceIR, set_to: T = None) -> T:
        return self._get_data(node, 'malformed_namespace', set_to)

    def ext(self, node: NodeIR, type: str, set_to: T = None) -> T:
        return self._get_data(node, type, set_to)


E = TypeVar('E', bound=Extension)
# endregion


# def _main():
#     import aizec.ir.nodes as nodes
#     node_names = set(nodes.__all__)
#     used_nodes = set()
#
#     for name, method in Extension.__dict__.items():
#         if not name.startswith("__") and isinstance(method, type(_main)):
#             try:
#                 node_type_str = method.__annotations__['node']
#             except KeyError:
#                 pass
#             else:
#                 used_nodes.add(node_type_str)
#
#     print(node_names - used_nodes)
#
#
# if __name__ == '__main__':
#     _main()
