from __future__ import annotations

from aizec.common import *

from aizec.aize_source import Position, Source


__all__ = [
    'NodeAST', 'TextAST',
    'ProgramAST', 'SourceAST',
    'ParamAST',
    'TopLevelAST', 'ClassAST', 'FunctionAST', 'ImportAST',
    'AttrAST', 'MethodSigAST', 'MethodImplAST',
    'StmtAST', 'IfStmtAST', 'WhileStmtAST', 'BlockStmtAST', 'VarDeclStmtAST', 'ReturnStmtAST', 'ExprStmtAST',

    'ExprAST', 'NEExprAST', 'BinaryExprAST', 'SubExprAST', 'AddExprAST', 'MulExprAST', 'GetVarExprAST', 'EQExprAST',
    'ModExprAST', 'LEExprAST', 'UnaryExprAST', 'LTExprAST', 'InvExprAST', 'NotExprAST', 'DivExprAST', 'GetAttrExprAST',
    'GEExprAST', 'SetAttrExprAST', 'NegExprAST', 'GTExprAST', 'SetVarExprAST', 'CallExprAST', 'StrLiteralAST',
    'IntLiteralAST'
]


class NodeAST:
    pass


class ProgramAST(NodeAST):
    def __init__(self, sources: List[SourceAST]):
        super().__init__()
        self.sources = sources


class SourceAST(NodeAST):
    def __init__(self, source: Source, top_levels: List[TopLevelAST]):
        super().__init__()

        self.source = source
        self.top_levels = top_levels

    @property
    def imports(self) -> List[ImportAST]:
        return [top_level for top_level in self.top_levels if isinstance(top_level, ImportAST)]


class TextAST(NodeAST):
    def __init__(self, pos: Position):
        self.pos = pos


class TopLevelAST(TextAST):
    pass


class ClassAST(TopLevelAST):
    def __init__(self, name: str, parents: List[ExprAST], body: List[ClassStmtAST], pos: Position):
        super().__init__(pos)

        self.name: str = name
        self.parents: List[ExprAST] = parents
        self.body: List[ClassStmtAST] = body


# class Trait(TopLevelAST):
#     def __init__(self, name: str, parents: List[TypeAnnotation], body: List[ClassStmt]):
#         super().__init__()
#
#         self.name: str = name
#         self.parents: List[TypeAnnotation] = parents
#         self.body: List[ClassStmt] = body


class ImportAST(TopLevelAST):
    def __init__(self, anchor: str, path: Path, pos: Position):
        super().__init__(pos)

        self.anchor: str = anchor
        self.path: Path = path


class FunctionAST(TopLevelAST):
    def __init__(self, name: str, params: List[ParamAST], ret: ExprAST, body: List[StmtAST], pos: Position):
        super().__init__(pos)

        self.name = name
        self.params = params
        self.ret = ret
        self.body = body


class ClassStmtAST(TextAST):
    pass


class AttrAST(ClassStmtAST):
    def __init__(self, name: str, annotation: ExprAST, pos: Position):
        super().__init__(pos)

        self.name = name
        self.annotation = annotation


class MethodSigAST(ClassStmtAST):
    def __init__(self, name: str, params: List[ParamAST], ret: ExprAST, pos: Position):
        super().__init__(pos)

        self.name = name
        self.params = params
        self.ret = ret


class MethodImplAST(MethodSigAST):
    def __init__(self, name: str, params: List[ParamAST], ret: ExprAST, body: List[StmtAST], pos: Position):
        super().__init__(name, params, ret, pos)

        self.body = body

    @classmethod
    def from_sig(cls, sig: MethodSigAST, body: List[StmtAST]) -> MethodImplAST:
        return cls(sig.name, sig.params, sig.ret, body, sig.pos)


class StmtAST(TextAST):
    pass


class IfStmtAST(StmtAST):
    def __init__(self, cond: ExprAST, then_do: StmtAST, else_do: StmtAST, pos: Position):
        super().__init__(pos)

        self.cond = cond
        self.then_do = then_do
        self.else_do = else_do


class WhileStmtAST(StmtAST):
    def __init__(self, cond: ExprAST, do: StmtAST, pos: Position):
        super().__init__(pos)

        self.cond = cond
        self.do = do


class BlockStmtAST(StmtAST):
    def __init__(self, body: List[StmtAST], pos: Position):
        super().__init__(pos)

        self.body = body


class VarDeclStmtAST(StmtAST):
    def __init__(self, name: str, annotation: ExprAST, value: ExprAST, pos: Position):
        super().__init__(pos)

        self.name = name
        self.annotation = annotation
        self.value = value


class ReturnStmtAST(StmtAST):
    def __init__(self, value: ExprAST, pos: Position):
        super().__init__(pos)

        self.value = value


class ExprStmtAST(StmtAST):
    def __init__(self, value: ExprAST, pos: Position):
        super().__init__(pos)

        self.value = value


class ExprAST(TextAST):
    pass


class GetVarExprAST(ExprAST):
    def __init__(self, var: str, pos: Position):
        super().__init__(pos)

        self.var = var


class SetVarExprAST(ExprAST):
    def __init__(self, var: str, value: ExprAST, pos: Position):
        super().__init__(pos)

        self.var = var
        self.value = value


class GetAttrExprAST(ExprAST):
    def __init__(self, obj: ExprAST, attr: str, pos: Position):
        super().__init__(pos)

        self.obj = obj
        self.attr = attr


class SetAttrExprAST(ExprAST):
    def __init__(self, obj: ExprAST, attr: str, value: ExprAST, pos: Position):
        super().__init__(pos)

        self.obj = obj
        self.attr = attr
        self.value = value


# region Binary

class BinaryExprAST(ExprAST):
    def __init__(self, left: ExprAST, right: ExprAST, pos: Position):
        super().__init__(pos)

        self.left = left
        self.right = right


class GTExprAST(BinaryExprAST):
    pass


class LTExprAST(BinaryExprAST):
    pass


class GEExprAST(BinaryExprAST):
    pass


class LEExprAST(BinaryExprAST):
    pass


class EQExprAST(BinaryExprAST):
    pass


class NEExprAST(BinaryExprAST):
    pass


class AddExprAST(BinaryExprAST):
    pass


class SubExprAST(BinaryExprAST):
    pass


class MulExprAST(BinaryExprAST):
    pass


class DivExprAST(BinaryExprAST):
    pass


class ModExprAST(BinaryExprAST):
    pass

# endregion


# region Unary

class UnaryExprAST(ExprAST):
    def __init__(self, right: ExprAST, pos: Position):
        super().__init__(pos)

        self.right = right


class InvExprAST(UnaryExprAST):
    pass


class NegExprAST(UnaryExprAST):
    pass


class NotExprAST(UnaryExprAST):
    pass

# endregion


class CallExprAST(ExprAST):
    def __init__(self, left: ExprAST, args: List[ExprAST], pos: Position):
        super().__init__(pos)

        self.left = left
        self.args = args


class IntLiteralAST(ExprAST):
    def __init__(self, num: int, pos: Position):
        super().__init__(pos)

        self.num = num


class StrLiteralAST(ExprAST):
    def __init__(self, s: str, pos: Position):
        super().__init__(pos)

        self.s = s


class ParamAST(TextAST):
    def __init__(self, name: str, annotation: ExprAST, pos: Position):
        super().__init__(pos)

        self.name = name
        self.annotation = annotation
