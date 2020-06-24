from __future__ import annotations

from aizec.common import *
from aizec.aize_common import Position, Source


__all__ = [
    'ASTVisitor',
    'NodeAST', 'TextAST',
    'ProgramAST', 'SourceAST',
    'TopLevelAST', 'FunctionAST', 'ImportAST', 'StructAST', 'UnionAST', 'VariantAST',
    'ParamAST', 'FunctionAttributeAST',
    'AggregateStmtAST', 'AggregateFieldAST', 'AggregateFunctionAST',
    'StmtAST', 'IfStmtAST', 'WhileStmtAST', 'BlockStmtAST', 'VarDeclStmtAST', 'ReturnStmtAST', 'ExprStmtAST',

    'ExprAST', 'CompareExprAST', 'BinaryExprAST', 'GetVarExprAST',
    'ArithmeticExprAST', 'UnaryExprAST', 'InvExprAST', 'NotExprAST', 'GetAttrExprAST',
    'SetAttrExprAST', 'NegExprAST', 'SetVarExprAST', 'CallExprAST', 'StrLiteralAST', 'NewExprAST',
    'IntLiteralAST', 'IntrinsicExprAST', 'LambdaExprAST', 'TupleExprAST', 'IsExprAST',

    'GetStaticAttrExprAST'
]


class ASTVisitor(ABC):
    def __init__(self, program: ProgramAST):
        self.program = program

    @abstractmethod
    def visit_program(self, program: ProgramAST):
        pass

    @abstractmethod
    def visit_source(self, source: SourceAST):
        pass

    def visit_top_level(self, top_level: TopLevelAST):
        if isinstance(top_level, FunctionAST):
            return self.visit_function(top_level)
        elif isinstance(top_level, StructAST):
            return self.visit_struct(top_level)
        elif isinstance(top_level, ImportAST):
            return self.visit_import(top_level)
        elif isinstance(top_level, UnionAST):
            return self.visit_union(top_level)
        else:
            raise TypeError(f"Expected a top-level node, got {top_level}")

    @abstractmethod
    def visit_union(self, union: UnionAST):
        pass

    @abstractmethod
    def visit_variant(self, variant: VariantAST):
        pass

    @abstractmethod
    def visit_import(self, imp: ImportAST):
        pass

    @abstractmethod
    def visit_struct(self, struct: StructAST):
        pass

    @abstractmethod
    def visit_function(self, func: FunctionAST):
        pass

    @abstractmethod
    def visit_agg_field(self, attr: AggregateFieldAST):
        pass

    @abstractmethod
    def visit_agg_func(self, func: AggregateFunctionAST):
        pass

    @abstractmethod
    def visit_param(self, param: ParamAST):
        pass

    @abstractmethod
    def visit_func_attr(self, attr: FunctionAttributeAST):
        pass

    def visit_stmt(self, stmt: StmtAST):
        if isinstance(stmt, ReturnStmtAST):
            return self.visit_return(stmt)
        elif isinstance(stmt, IfStmtAST):
            return self.visit_if(stmt)
        elif isinstance(stmt, BlockStmtAST):
            return self.visit_block(stmt)
        elif isinstance(stmt, VarDeclStmtAST):
            return self.visit_var_decl(stmt)
        elif isinstance(stmt, ExprStmtAST):
            return self.visit_expr_stmt(stmt)
        elif isinstance(stmt, WhileStmtAST):
            return self.visit_while(stmt)
        else:
            raise TypeError(f"Expected a stmt node, got {stmt}")

    @abstractmethod
    def visit_expr_stmt(self, stmt: ExprStmtAST):
        pass

    @abstractmethod
    def visit_var_decl(self, decl: VarDeclStmtAST):
        pass

    @abstractmethod
    def visit_block(self, block: BlockStmtAST):
        pass

    @abstractmethod
    def visit_if(self, if_: IfStmtAST):
        pass

    @abstractmethod
    def visit_while(self, while_: WhileStmtAST):
        pass

    @abstractmethod
    def visit_return(self, ret: ReturnStmtAST):
        pass

    def visit_expr(self, expr: ExprAST):
        if isinstance(expr, IntLiteralAST):
            return self.visit_int(expr)
        elif isinstance(expr, IntrinsicExprAST):
            return self.visit_intrinsic(expr)
        elif isinstance(expr, NewExprAST):
            return self.visit_new(expr)
        elif isinstance(expr, CallExprAST):
            return self.visit_call(expr)
        elif isinstance(expr, GetVarExprAST):
            return self.visit_get_var(expr)
        elif isinstance(expr, SetVarExprAST):
            return self.visit_set_var(expr)
        elif isinstance(expr, GetAttrExprAST):
            return self.visit_get_attr(expr)
        elif isinstance(expr, SetAttrExprAST):
            return self.visit_set_attr(expr)
        elif isinstance(expr, CompareExprAST):
            return self.visit_cmp(expr)
        elif isinstance(expr, ArithmeticExprAST):
            return self.visit_arith(expr)
        elif isinstance(expr, NegExprAST):
            return self.visit_neg(expr)
        elif isinstance(expr, GetStaticAttrExprAST):
            return self.visit_static_attr_expr(expr)
        elif isinstance(expr, LambdaExprAST):
            return self.visit_lambda(expr)
        elif isinstance(expr, TupleExprAST):
            return self.visit_tuple(expr)
        elif isinstance(expr, IsExprAST):
            return self.visit_is(expr)
        else:
            raise TypeError(f"Expected a expr node, got {expr}")

    @abstractmethod
    def visit_is(self, is_: IsExprAST):
        pass

    @abstractmethod
    def visit_cmp(self, cmp: CompareExprAST):
        pass

    @abstractmethod
    def visit_arith(self, arith: ArithmeticExprAST):
        pass

    @abstractmethod
    def visit_neg(self, neg: NegExprAST):
        pass

    @abstractmethod
    def visit_call(self, call: CallExprAST):
        pass

    @abstractmethod
    def visit_new(self, new: NewExprAST):
        pass

    @abstractmethod
    def visit_get_var(self, get_var: GetVarExprAST):
        pass

    @abstractmethod
    def visit_set_var(self, set_var: SetVarExprAST):
        pass

    @abstractmethod
    def visit_get_attr(self, get_attr: GetAttrExprAST):
        pass

    @abstractmethod
    def visit_set_attr(self, set_attr: SetAttrExprAST):
        pass

    @abstractmethod
    def visit_static_attr_expr(self, static_attr: GetStaticAttrExprAST):
        pass

    @abstractmethod
    def visit_intrinsic(self, intrinsic: IntrinsicExprAST):
        pass

    @abstractmethod
    def visit_tuple(self, tuple: TupleExprAST):
        pass

    @abstractmethod
    def visit_lambda(self, lambda_: LambdaExprAST):
        pass

    @abstractmethod
    def visit_int(self, num: IntLiteralAST):
        pass

    def visit_namespace(self, namespace: ExprAST):
        if isinstance(namespace, GetVarExprAST):
            return self.visit_get_namespace(namespace)
        else:
            return self.handle_malformed_namespace(namespace)

    @abstractmethod
    def visit_get_namespace(self, namespace: GetVarExprAST):
        pass

    @abstractmethod
    def handle_malformed_namespace(self, namespace: ExprAST):
        pass

    @abstractmethod
    def visit_ann(self, ann: ExprAST):
        pass

    def visit_type(self, type: ExprAST):
        if isinstance(type, GetVarExprAST):
            return self.visit_get_type(type)
        elif isinstance(type, LambdaExprAST):
            return self.visit_func_type(type)
        elif isinstance(type, TupleExprAST):
            return self.visit_tuple_type(type)
        elif type is None:
            return self.visit_no_type()
        else:
            return self.handle_malformed_type(type)

    @abstractmethod
    def visit_no_type(self):
        pass

    @abstractmethod
    def visit_get_type(self, type: GetVarExprAST):
        pass

    @abstractmethod
    def visit_func_type(self, func_type: LambdaExprAST):
        pass

    @abstractmethod
    def visit_tuple_type(self, tuple_: TupleExprAST):
        pass

    @abstractmethod
    def handle_malformed_type(self, type: ExprAST):
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


class StructAST(TopLevelAST):
    def __init__(self, name: str, body: List[AggregateStmtAST], pos: Position):
        super().__init__(pos)

        self.name = name
        self.body = body


class UnionAST(TopLevelAST):
    def __init__(self, name: str, variants: List[VariantAST], funcs: List[AggregateFunctionAST], pos: Position):
        super().__init__(pos)

        self.name = name
        self.variants = variants
        self.funcs = funcs


class VariantAST(TopLevelAST):
    def __init__(self, name: str, type: ExprAST, pos: Position):
        super().__init__(pos)

        self.name = name
        self.type = type


class ImportAST(TopLevelAST):
    def __init__(self, anchor: str, path: Path, pos: Position):
        super().__init__(pos)

        self.anchor: str = anchor
        self.path: Path = path
        self.source: Optional[Source] = None


class FunctionAST(TopLevelAST):
    def __init__(self, name: str, params: List[ParamAST], ret: ExprAST, body: List[StmtAST], attributes: List[FunctionAttributeAST], pos: Position):
        super().__init__(pos)

        self.name = name
        self.params = params
        self.ret = ret
        self.body = body
        self.attributes = attributes


class AggregateStmtAST(TextAST):
    pass


class AggregateFieldAST(AggregateStmtAST):
    def __init__(self, name: str, annotation: ExprAST, pos: Position):
        super().__init__(pos)

        self.name = name
        self.annotation = annotation


class AggregateFunctionAST(AggregateStmtAST):
    def __init__(self, name: str, params: List[ParamAST], ret: ExprAST, attrs: List[FunctionAttributeAST], body: List[StmtAST], pos: Position):
        super().__init__(pos)

        self.name = name
        self.params = params
        self.ret = ret

        self.body = body


class ParamAST(TextAST):
    def __init__(self, name: str, annotation: Optional[ExprAST], pos: Position):
        super().__init__(pos)

        self.name = name
        self.annotation = annotation


class FunctionAttributeAST(TextAST):
    def __init__(self, name: str, pos: Position):
        super().__init__(pos)
        self.name = name


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


class LambdaExprAST(ExprAST):
    def __init__(self, params: List[ParamAST], body: ExprAST, pos: Position):
        super().__init__(pos)

        self.params = params
        self.body = body


class TupleExprAST(ExprAST):
    def __init__(self, items: List[ExprAST], pos: Position):
        super().__init__(pos)

        self.items = items


class IsExprAST(ExprAST):
    def __init__(self, expr: ExprAST, variant: str, to_var: str, pos: Position):
        super().__init__(pos)

        self.expr = expr
        self.variant = variant
        self.to_var = to_var


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
    def __init__(self, op: str, left: ExprAST, right: ExprAST, pos: Position):
        super().__init__(pos)

        self.op = op
        self.left = left
        self.right = right


class CompareExprAST(BinaryExprAST):
    pass


class ArithmeticExprAST(BinaryExprAST):
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


class GetStaticAttrExprAST(ExprAST):
    def __init__(self, namespace: ExprAST, attr: str, pos: Position):
        super().__init__(pos)

        self.namespace = namespace
        self.attr = attr


class NewExprAST(ExprAST):
    def __init__(self, type: GetVarExprAST, args: List[ExprAST], pos: Position):
        super().__init__(pos)

        self.type = type
        self.args = args


class CallExprAST(ExprAST):
    def __init__(self, left: ExprAST, args: List[ExprAST], pos: Position):
        super().__init__(pos)

        self.left = left
        self.args = args


class IntrinsicExprAST(ExprAST):
    def __init__(self, name: str, args: List[ExprAST], pos: Position):
        super().__init__(pos)

        self.name = name
        self.args = args


class IntLiteralAST(ExprAST):
    def __init__(self, num: int, pos: Position):
        super().__init__(pos)

        self.num = num


class StrLiteralAST(ExprAST):
    def __init__(self, s: str, pos: Position):
        super().__init__(pos)

        self.s = s
