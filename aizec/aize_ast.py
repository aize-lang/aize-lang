from __future__ import annotations

from aizec.common import *

from aizec.aize_source import *


__all__ = [
    'ASTVisitor',
    'NodeAST', 'TextAST',
    'ProgramAST', 'SourceAST',
    'ParamAST',
    'TopLevelAST', 'ClassAST', 'FunctionAST', 'ImportAST',
    'AttrAST', 'MethodSigAST', 'MethodImplAST', 'MethodAST',
    'StmtAST', 'IfStmtAST', 'WhileStmtAST', 'BlockStmtAST', 'VarDeclStmtAST', 'ReturnStmtAST', 'ExprStmtAST',

    'ExprAST', 'NEExprAST', 'BinaryExprAST', 'SubExprAST', 'AddExprAST', 'MulExprAST', 'GetVarExprAST', 'EQExprAST',
    'ModExprAST', 'LEExprAST', 'UnaryExprAST', 'LTExprAST', 'InvExprAST', 'NotExprAST', 'DivExprAST', 'GetAttrExprAST',
    'GEExprAST', 'SetAttrExprAST', 'NegExprAST', 'GTExprAST', 'SetVarExprAST', 'CallExprAST', 'StrLiteralAST',
    'IntLiteralAST'
]


class ASTVisitor(ABC):
    def __init__(self, program: ProgramAST):
        self.program = program

    @abstractmethod
    def handle_malformed_type(self, type: ExprAST):
        pass

    @abstractmethod
    def visit_program(self, program: ProgramAST):
        pass

    @abstractmethod
    def visit_source(self, source: SourceAST):
        pass

    def visit_top_level(self, top_level: TopLevelAST):
        if isinstance(top_level, ClassAST):
            return self.visit_class(top_level)
        elif isinstance(top_level, FunctionAST):
            return self.visit_function(top_level)
        else:
            raise TypeError(f"Expected a top-level node, got {top_level}")

    @abstractmethod
    def visit_class(self, cls: ClassAST):
        pass

    @abstractmethod
    def visit_function(self, func: FunctionAST):
        pass

    @abstractmethod
    def visit_attr(self, attr: AttrAST):
        pass

    def visit_method(self, method: MethodAST):
        if isinstance(method, MethodImplAST):
            return self.visit_method_impl(method)
        elif isinstance(method, MethodSigAST):
            return self.visit_method_sig(method)
        else:
            raise TypeError(f"Expected a method node, got {method}")

    @abstractmethod
    def visit_method_impl(self, method: MethodImplAST):
        pass

    @abstractmethod
    def visit_method_sig(self, method: MethodSigAST):
        pass

    @abstractmethod
    def visit_param(self, param: ParamAST):
        pass

    def visit_stmt(self, stmt: StmtAST):
        if isinstance(stmt, ReturnStmtAST):
            return self.visit_return(stmt)
        elif isinstance(stmt, IfStmtAST):
            return self.visit_if(stmt)
        elif isinstance(stmt, BlockStmtAST):
            return self.visit_block(stmt)
        else:
            raise TypeError(f"Expected a stmt node, got {stmt}")

    @abstractmethod
    def visit_block(self, block: BlockStmtAST):
        pass

    @abstractmethod
    def visit_if(self, if_: IfStmtAST):
        pass

    @abstractmethod
    def visit_return(self, ret: ReturnStmtAST):
        pass

    def visit_expr(self, expr: ExprAST):
        if isinstance(expr, IntLiteralAST):
            return self.visit_int(expr)
        elif isinstance(expr, CallExprAST):
            return self.visit_call(expr)
        elif isinstance(expr, GetVarExprAST):
            return self.visit_get_var(expr)
        elif isinstance(expr, LTExprAST):
            return self.visit_lt(expr)
        elif isinstance(expr, AddExprAST):
            return self.visit_add(expr)
        elif isinstance(expr, SubExprAST):
            return self.visit_sub(expr)
        else:
            raise TypeError(f"Expected a expr node, got {expr}")

    @abstractmethod
    def visit_lt(self, lt: LTExprAST):
        pass

    @abstractmethod
    def visit_add(self, add: AddExprAST):
        pass

    @abstractmethod
    def visit_sub(self, sub: SubExprAST):
        pass

    @abstractmethod
    def visit_call(self, call: CallExprAST):
        pass

    @abstractmethod
    def visit_get_var(self, get_var: GetVarExprAST):
        pass

    @abstractmethod
    def visit_int(self, num: IntLiteralAST):
        pass

    @abstractmethod
    def visit_ann(self, ann: ExprAST):
        pass

    def visit_type(self, type: ExprAST):
        if isinstance(type, GetVarExprAST):
            return self.visit_get_type(type)
        else:
            return self.handle_malformed_type(type)

    @abstractmethod
    def visit_get_type(self, type: GetVarExprAST):
        pass


class NodeAST:
    def __eq__(self, other):
        return other is self

    def __hash__(self):
        return id(self)


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


MethodAST = MethodSigAST


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
