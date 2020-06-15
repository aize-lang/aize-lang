from __future__ import annotations

from aizec.common import *

from aizec.aize_ast import *
from aizec.aize_source import *


__all__ = [
    'IR',

    'Extension',

    'NodeIR', 'TextIR',
    'ProgramIR', 'SourceIR',
    'TopLevelIR', 'FunctionIR', 'ClassIR',
    'FieldIR', 'MethodDeclIR', 'MethodDefIR',
    'ParamIR',
    'StmtIR','ReturnIR', 'IfStmtIR', 'BlockIR',
    'ExprIR', 'CallIR', 'IntIR', 'GetVarIR', 'CompareIR', 'ArithmeticIR',
    'AnnotationIR',
    'TypeIR', 'GetTypeIR', 'MalformedTypeIR',
]


T = TypeVar('T')


class IR:
    def __init__(self, program: ProgramIR):
        self.program = program
        self.extensions: Dict[Type[Extension], Extension] = {}
        self.ran_passes: Set = set()

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

        def visit_block(self, block: BlockStmtAST):
            return BlockIR([self.visit_stmt(stmt) for stmt in block.body], block.pos)

        def visit_if(self, if_: IfStmtAST):
            return IfStmtIR(self.visit_expr(if_.cond), self.visit_stmt(if_.then_do), self.visit_stmt(if_.else_do), if_.pos)

        def visit_return(self, ret: ReturnStmtAST):
            return ReturnIR(self.visit_expr(ret.value), ret.pos)

        def visit_lt(self, lt: LTExprAST):
            return CompareIR("<", self.visit_expr(lt.left), self.visit_expr(lt.right), lt.pos)

        def visit_add(self, add: AddExprAST):
            return ArithmeticIR("+", self.visit_expr(add.left), self.visit_expr(add.right), add.pos)

        def visit_sub(self, sub: SubExprAST):
            return ArithmeticIR("-", self.visit_expr(sub.left), self.visit_expr(sub.right), sub.pos)

        def visit_call(self, call: CallExprAST):
            return CallIR(self.visit_expr(call.left), [self.visit_expr(arg) for arg in call.args], call.pos)

        def visit_get_var(self, get_var: GetVarExprAST):
            return GetVarIR(get_var.var, get_var.pos)

        def visit_int(self, literal: IntLiteralAST):
            return IntIR(literal.num, literal.pos)

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
    def type(self, node: TypeIR, set_to: T = None) -> T:
        return self._get_data(node, 'type', set_to)

    def ext(self, node: NodeIR, type: str, set_to: T = None) -> T:
        return self._get_data(node, type, set_to)


E = TypeVar('E', bound=Extension)
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


class BlockIR(StmtIR):
    def __init__(self, stmts: List[StmtIR], pos: Position):
        super().__init__(pos)
        self.stmts = stmts


class IfStmtIR(StmtIR):
    def __init__(self, cond: ExprIR, then_do: StmtIR, else_do: StmtIR, pos: Position):
        super().__init__(pos)
        self.cond = cond
        self.then_do = then_do
        self.else_do = else_do


class ReturnIR(StmtIR):
    def __init__(self, expr: ExprIR, pos: Position):
        super().__init__(pos)
        self.expr = expr
# endregion


# region Expression Nodes
class ExprIR(TextIR):
    pass


class CompareIR(ExprIR):
    def __init__(self, op: str, left: ExprIR, right: ExprIR, pos: Position):
        super().__init__(pos)
        self.op = op
        self.left = left
        self.right = right


class ArithmeticIR(ExprIR):
    def __init__(self, op: str, left: ExprIR, right: ExprIR, pos: Position):
        super().__init__(pos)
        self.op = op
        self.left = left
        self.right = right


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
