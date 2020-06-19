from __future__ import annotations

from aizec.common import *
from aizec.aize_common import Position, Source


__all__ = [
    'NodeIR', 'TextIR',
    'ProgramIR', 'SourceIR',
    'TopLevelIR', 'FunctionIR', 'StructIR', 'ImportIR',
    'AggFieldIR', 'AggFuncIR',
    'ParamIR', 'FuncAttrIR',
    'StmtIR','ReturnIR', 'IfStmtIR', 'BlockIR', 'VarDeclIR', 'ExprStmtIR', 'WhileStmtIR',
    'ExprIR', 'CallIR', 'IntIR', 'GetVarIR', 'SetVarIR', 'CompareIR', 'ArithmeticIR', 'NewIR', 'GetAttrIR', 'SetAttrIR',
    'IntrinsicIR', 'GetStaticAttrExprIR', 'NegateIR', 'CastIntIR', 'MethodCallIR',
    'AnnotationIR',
    'TypeIR', 'GetTypeIR', 'MalformedTypeIR', 'GeneratedTypeIR', 'NoTypeIR',
    'NamespaceIR', 'GetNamespaceIR', 'MalformedNamespaceIR',
]


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


class ImportIR(TopLevelIR):
    def __init__(self, source: Source, path: Path, pos: Position):
        super().__init__(pos)
        self.source = source
        self.path = path

        self.source_ir: Optional[SourceIR] = None


class FunctionIR(TopLevelIR):
    def __init__(self, name: str, params: List[ParamIR], ret: TypeIR, body: List[StmtIR], attrs: List[FuncAttrIR], pos: Position):
        super().__init__(pos)
        self.name = name
        self.params = params
        self.ret = ret
        self.body = body
        self.attrs = attrs


class StructIR(TopLevelIR):
    def __init__(self, name: str, fields: List[AggFieldIR], funcs: List[AggFuncIR], pos: Position):
        super().__init__(pos)

        self.name = name
        self.fields = fields
        self.funcs = funcs


# region Aggregate Statement Nodes
class AggFieldIR(TextIR):
    def __init__(self, name: str, type: TypeIR, pos: Position):
        super().__init__(pos)
        self.name = name
        self.type = type


class AggFuncIR(TextIR):
    def __init__(self, name: str, params: List[ParamIR], ret: TypeIR, body: List[StmtIR], pos: Position):
        super().__init__(pos)

        self.name = name
        self.params = params
        self.ret = ret
        self.body = body
# endregion
# endregion


# region Function Other Node
class ParamIR(TextIR):
    def __init__(self, name: str, type: TypeIR, pos: Position):
        super().__init__(pos)
        self.name = name
        self.type = type


class FuncAttrIR(TextIR):
    def __init__(self, name: str, pos: Position):
        super().__init__(pos)
        self.name = name
# endregion


# region Statement Nodes
class StmtIR(TextIR):
    pass


class VarDeclIR(StmtIR):
    def __init__(self, name: str, ann: AnnotationIR, value: ExprIR, pos: Position):
        super().__init__(pos)
        self.name = name
        self.ann = ann
        self.value = value


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


class WhileStmtIR(StmtIR):
    def __init__(self, cond: ExprIR, while_do: StmtIR, pos: Position):
        super().__init__(pos)

        self.cond = cond
        self.while_do = while_do


class ExprStmtIR(StmtIR):
    def __init__(self, expr: ExprIR, pos: Position):
        super().__init__(pos)
        self.expr = expr


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


class NegateIR(ExprIR):
    def __init__(self, right: ExprIR, pos: Position):
        super().__init__(pos)
        self.right = right


class NewIR(ExprIR):
    def __init__(self, type: GetTypeIR, arguments: List[ExprIR], pos: Position):
        super().__init__(pos)

        self.type = type
        self.arguments = arguments


class CallIR(ExprIR):
    def __init__(self, callee: ExprIR, arguments: List[ExprIR], pos: Position):
        super().__init__(pos)
        self.callee = callee
        self.arguments = arguments


class MethodCallIR(ExprIR):
    def __init__(self, obj: ExprIR, attr: str, arguments: List[ExprIR], pos: Position):
        super().__init__(pos)
        self.obj = obj
        self.attr = attr
        self.arguments = arguments


class GetVarIR(ExprIR):
    def __init__(self, var_name: str, pos: Position):
        super().__init__(pos)
        self.var_name = var_name


class SetVarIR(ExprIR):
    def __init__(self, var_name: str, value: ExprIR, pos: Position):
        super().__init__(pos)
        self.var_name = var_name
        self.value = value


class GetAttrIR(ExprIR):
    def __init__(self, obj: ExprIR, attr: str, pos: Position):
        super().__init__(pos)

        self.obj = obj
        self.attr = attr


class GetStaticAttrExprIR(ExprIR):
    def __init__(self, namespace: NamespaceIR, attr: str, pos: Position):
        super().__init__(pos)

        self.namespace = namespace
        self.attr = attr


class SetAttrIR(ExprIR):
    def __init__(self, obj: ExprIR, attr: str, value: ExprIR, pos: Position):
        super().__init__(pos)

        self.obj = obj
        self.attr = attr
        self.value = value


class IntrinsicIR(ExprIR):
    def __init__(self, name: str, args: List[ExprIR], pos: Position):
        super().__init__(pos)

        self.name = name
        self.args = args


class CastIntIR(ExprIR):
    def __init__(self, expr: ExprIR, type: TypeIR, pos: Position):
        super().__init__(pos)

        self.expr = expr
        self.type = type


class IntIR(ExprIR):
    def __init__(self, num: int, pos: Position):
        super().__init__(pos)
        self.num = num
# endregion


# region Namespace Nodes
class NamespaceIR(TextIR):
    pass


class GetNamespaceIR(NamespaceIR):
    def __init__(self, name: str, pos: Position):
        super().__init__(pos)

        self.name = name


class MalformedNamespaceIR(NamespaceIR):
    def __init__(self, pos: Position):
        super().__init__(pos)
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


class NoTypeIR(TypeIR):
    def __init__(self):
        super().__init__(Position.new_none())


class GeneratedTypeIR(TypeIR):
    def __init__(self, pos: Position):
        super().__init__(pos)
# endregion


# if __name__ == '__main__':
#     __all__ = ['NodeIR', 'WithNamespace', 'ProgramData'] + [child.__name__ for child in all_subclasses(NodeIR)]
#     print(__all__)
