from __future__ import annotations

from aizec.common import *

from .nodes import *
from .extensions import Extension

from aizec.aize_common import Source, Position
from aizec.aize_frontend.aize_ast import *


__all__ = [
    'IR', 'Extension',
]


class IR:
    def __init__(self, program: ProgramIR):
        self.program = program
        self.extensions: Dict[Type[Extension], Extension] = {}
        self.ran_passes: Set = set()

    @classmethod
    def from_ast(cls, program: ProgramAST) -> IR:
        return cls(CreateIR(program).visit_program(program))


# region IR Creator
class CreateIR(ASTVisitor):
    def __init__(self, program: ProgramAST):
        super().__init__(program)

        self.sources: Dict[Source, SourceIR] = {}

    def visit_program(self, program: ProgramAST) -> ProgramIR:
        program = ProgramIR([self.visit_source(source) for source in program.sources])
        for source in program.sources:
            for top_level in source.top_levels:
                if isinstance(top_level, ImportIR):
                    top_level.source_ir = self.sources[top_level.source]
        return program

    def visit_source(self, source: SourceAST):
        source_ir = SourceIR([self.visit_top_level(top_level) for top_level in source.top_levels], source.source.get_name())
        self.sources[source.source] = source_ir
        return source_ir

    def visit_import(self, imp: ImportAST):
        return ImportIR(imp.source, imp.path, imp.pos)

    def visit_function(self, func: FunctionAST):
        ann = self.visit_ann(func.ret)
        return FunctionIR(
            name=func.name,
            params=[self.visit_param(param) for param in func.params],
            ret=ann.type,
            body=[self.visit_stmt(stmt) for stmt in func.body],
            attrs=[self.visit_func_attr(attr) for attr in func.attributes],
            pos=func.pos
        )

    def visit_struct(self, struct: StructAST):
        fields = []
        funcs = []
        for stmt in struct.body:
            if isinstance(stmt, AggregateFieldAST):
                fields.append(self.visit_agg_field(stmt))
            elif isinstance(stmt, AggregateFunctionAST):
                funcs.append(self.visit_agg_func(stmt))
            else:
                raise Exception()
        return StructIR(struct.name, fields, funcs, struct.pos)

    def visit_union(self, union: UnionAST):
        return UnionIR(union.name, [self.visit_variant(variant) for variant in union.variants], [self.visit_agg_func(func) for func in union.funcs], union.pos)

    def visit_variant(self, variant: VariantAST):
        return VariantIR(variant.name, self.visit_type(variant.type), variant.pos)

    def visit_agg_field(self, attr: AggregateFieldAST):
        ann = self.visit_ann(attr.annotation)
        return AggFieldIR(attr.name, ann.type, attr.pos)

    def visit_agg_func(self, func: AggregateFunctionAST):
        return AggFuncIR(
            func.name,
            [self.visit_param(param) for param in func.params],
            self.visit_type(func.ret),
            [self.visit_stmt(stmt) for stmt in func.body],
            func.pos
        )

    def visit_param(self, param: ParamAST):
        ann = self.visit_ann(param.annotation)
        return ParamIR(
            name=param.name,
            type=ann.type,
            pos=param.pos
        )

    def visit_func_attr(self, attr: FunctionAttributeAST):
        return FuncAttrIR(attr.name, attr.pos)

    def visit_var_decl(self, decl: VarDeclStmtAST):
        return VarDeclIR(decl.name, self.visit_ann(decl.annotation), self.visit_expr(decl.value), decl.pos)

    def visit_block(self, block: BlockStmtAST):
        return BlockIR([self.visit_stmt(stmt) for stmt in block.body], block.pos)

    def visit_if(self, if_: IfStmtAST):
        return IfStmtIR(self.visit_expr(if_.cond), self.visit_stmt(if_.then_do), self.visit_stmt(if_.else_do), if_.pos)

    def visit_while(self, while_: WhileStmtAST):
        return WhileStmtIR(self.visit_expr(while_.cond), self.visit_stmt(while_.do), while_.pos)

    def visit_expr_stmt(self, stmt: ExprStmtAST):
        return ExprStmtIR(self.visit_expr(stmt.value), stmt.pos)

    def visit_return(self, ret: ReturnStmtAST):
        return ReturnIR(self.visit_expr(ret.value), ret.pos)

    def visit_is(self, is_: IsExprAST):
        return IsIR(self.visit_expr(is_.expr), is_.variant, is_.to_var, is_.pos)

    def visit_cmp(self, cmp: CompareExprAST):
        return CompareIR(cmp.op, self.visit_expr(cmp.left), self.visit_expr(cmp.right), cmp.pos)

    def visit_arith(self, arith: ArithmeticExprAST):
        return ArithmeticIR(arith.op, self.visit_expr(arith.left), self.visit_expr(arith.right), arith.pos)

    def visit_neg(self, neg: NegExprAST):
        return NegateIR(self.visit_expr(neg.right), neg.pos)

    def visit_new(self, new: NewExprAST):
        return NewIR(self.visit_get_type(new.type), [self.visit_expr(arg) for arg in new.args], new.pos)

    def visit_call(self, call: CallExprAST):
        return CallIR(self.visit_expr(call.left), [self.visit_expr(arg) for arg in call.args], call.pos)

    def visit_set_var(self, set_var: SetVarExprAST):
        return SetVarIR(set_var.var, self.visit_expr(set_var.value), set_var.pos)

    def visit_get_var(self, get_var: GetVarExprAST):
        return GetVarIR(get_var.var, get_var.pos)

    def visit_get_attr(self, get_attr: GetAttrExprAST):
        return GetAttrIR(self.visit_expr(get_attr.obj), get_attr.attr, get_attr.pos)

    def visit_set_attr(self, set_attr: SetAttrExprAST):
        return SetAttrIR(self.visit_expr(set_attr.obj), set_attr.attr, self.visit_expr(set_attr.value), set_attr.pos)

    def visit_static_attr_expr(self, static_attr: GetStaticAttrExprAST):
        return GetStaticAttrExprIR(self.visit_namespace(static_attr.namespace), static_attr.attr, static_attr.pos)

    def visit_intrinsic(self, intrinsic: IntrinsicExprAST):
        return IntrinsicIR(intrinsic.name, [self.visit_expr(arg) for arg in intrinsic.args], intrinsic.pos)

    def visit_lambda(self, lambda_: LambdaExprAST):
        return LambdaIR([self.visit_param(param) for param in lambda_.params], self.visit_expr(lambda_.body), lambda_.pos)

    def visit_tuple(self, tuple: TupleExprAST):
        return TupleIR([self.visit_expr(item) for item in tuple.items], tuple.pos)

    def visit_int(self, literal: IntLiteralAST):
        return IntIR(literal.num, literal.pos)

    def visit_get_namespace(self, namespace: GetVarExprAST):
        return GetNamespaceIR(namespace.var, namespace.pos)

    def handle_malformed_namespace(self, namespace: ExprAST):
        return MalformedNamespaceIR(namespace.pos)

    def visit_ann(self, ann: ExprAST):
        return AnnotationIR(self.visit_type(ann), ann.pos if ann else Position.new_none())

    def handle_malformed_type(self, type: ExprAST):
        return MalformedTypeIR(type.pos)

    def visit_no_type(self):
        return NoTypeIR()

    def visit_get_type(self, type: GetVarExprAST):
        return GetTypeIR(type.var, type.pos)

    def visit_func_type(self, func_type: LambdaExprAST):
        return FuncTypeIR([self.visit_type(param.annotation).type for param in func_type.params], self.visit_type(func_type.body), func_type.pos)

    def visit_tuple_type(self, tuple_: TupleExprAST):
        return TupleTypeIR([self.visit_type(item) for item in tuple_.items], tuple_.pos)
# endregion
