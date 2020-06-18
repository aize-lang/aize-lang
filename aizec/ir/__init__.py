from __future__ import annotations

from aizec.common import *

from .ir_nodes import *
from .extensions import Extension

from aizec.aize_common.aize_source import Source
from aizec.aize_frontend.aize_ast import *


__all__ = [
    'IR',

    'Extension',

    'NodeIR', 'TextIR',
    'ProgramIR', 'SourceIR',
    'TopLevelIR', 'FunctionIR', 'ClassIR', 'StructIR', 'ImportIR',
    'FieldIR', 'MethodDeclIR', 'MethodDefIR',
    'ParamIR',
    'StmtIR','ReturnIR', 'IfStmtIR', 'BlockIR', 'VarDeclIR', 'ExprStmtIR',
    'ExprIR', 'CallIR', 'IntIR', 'GetVarIR', 'SetVarIR', 'CompareIR', 'ArithmeticIR', 'NewIR', 'GetAttrIR', 'SetAttrIR',
    'IntrinsicIR', 'GetStaticAttrExprIR', 'NegateIR',
    'AnnotationIR',
    'TypeIR', 'GetTypeIR', 'MalformedTypeIR',
    'NamespaceIR', 'GetNamespaceIR', 'MalformedNamespaceIR',
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
            pos=func.pos
        )

    def visit_struct(self, struct: StructAST):
        fields = []
        for attr in struct.attrs:
            fields.append(self.visit_attr(attr))
        return StructIR(struct.name, fields, struct.pos)

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

    def visit_var_decl(self, decl: VarDeclStmtAST):
        return VarDeclIR(decl.name, self.visit_ann(decl.annotation), self.visit_expr(decl.value), decl.pos)

    def visit_block(self, block: BlockStmtAST):
        return BlockIR([self.visit_stmt(stmt) for stmt in block.body], block.pos)

    def visit_if(self, if_: IfStmtAST):
        return IfStmtIR(self.visit_expr(if_.cond), self.visit_stmt(if_.then_do), self.visit_stmt(if_.else_do), if_.pos)

    def visit_expr_stmt(self, stmt: ExprStmtAST):
        return ExprStmtIR(self.visit_expr(stmt.value), stmt.pos)

    def visit_return(self, ret: ReturnStmtAST):
        return ReturnIR(self.visit_expr(ret.value), ret.pos)

    def visit_lt(self, lt: LTExprAST):
        return CompareIR("<", self.visit_expr(lt.left), self.visit_expr(lt.right), lt.pos)

    def visit_add(self, add: AddExprAST):
        return ArithmeticIR("+", self.visit_expr(add.left), self.visit_expr(add.right), add.pos)

    def visit_sub(self, sub: SubExprAST):
        return ArithmeticIR("-", self.visit_expr(sub.left), self.visit_expr(sub.right), sub.pos)

    def visit_mul(self, mul: MulExprAST):
        return ArithmeticIR("*", self.visit_expr(mul.left), self.visit_expr(mul.right), mul.pos)

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

    def visit_int(self, literal: IntLiteralAST):
        return IntIR(literal.num, literal.pos)

    def visit_get_namespace(self, namespace: GetVarExprAST):
        return GetNamespaceIR(namespace.var, namespace.pos)

    def handle_malformed_namespace(self, namespace: ExprAST):
        return MalformedNamespaceIR(namespace.pos)

    def visit_ann(self, ann: ExprAST):
        return AnnotationIR(self.visit_type(ann), ann.pos)

    def handle_malformed_type(self, type: ExprAST):
        return MalformedTypeIR(type.pos)

    def visit_get_type(self, type: GetVarExprAST):
        return GetTypeIR(type.var, type.pos)
# endregion
