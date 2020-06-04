from __future__ import annotations

from aizec.common import *

from aizec.aize_ast import *
from aizec.aize_ir import *

from aizec.aize_error import AizeMessage, Reporter, MessageHandler
from aizec.aize_source import *
from aizec.aize_symbols import *


# region Errors
# class DefinitionError(AizeMessage):
#     def __init__(self, msg: str, pos: Position, note: AizeMessage = None):
#         super().__init__(self.ERROR)
#         self.msg = msg
#         self.pos = pos
#
#         self.note = note
#
#     @classmethod
#     def name_existing(cls, node: Node, existing: Symbol):
#         note = DefinitionNote.from_node(existing.node, "Previously defined here")
#         error = cls.from_node(node, f"Name '{existing.name}' already defined", note)
#         return error
#
#     @classmethod
#     def name_undefined(cls, node: Node, name: str):
#         error = cls.from_node(node, f"Name '{name}' could not be found")
#         return error
#
#     @classmethod
#     def param_repeated(cls, func: Node, param: Node, name: str):
#         note = DefinitionNote.from_node(param, "Repeated here")
#         error = cls.from_node(func, f"Parameter name '{name}' repeated", note)
#         return error
#
#     @classmethod
#     def from_node(cls, node: Node, msg: str, note: AizeMessage = None):
#         pos = Position.of(node)
#         return cls(pos.get_source_name(), pos, msg, note)
#
#     def display(self, reporter: Reporter):
#         reporter.positioned_error("Name Resolution Error", self.msg, self.pos)
#         if self.note is not None:
#             reporter.separate()
#             with reporter.indent():
#                 self.note.display(reporter)
#
#
# class TypeCheckingError(AizeMessage):
#     def __init__(self, source_name: str, pos: Position, msg: str, note: AizeMessage = None):
#         super().__init__(self.ERROR)
#         self.source = source_name
#         self.pos = pos
#         self.msg = msg
#
#         self.note = note
#
#     @classmethod
#     def from_nodes(cls, definition: Node, offender: Node):
#         offender_pos = Position.of(offender)
#         def_pos = Position.of(definition)
#         note = DefinitionNote.from_node(definition, "Declared here")
#         error = cls(offender_pos.get_source_name(), offender_pos, "Expected type , got type", note)
#         return error
#
#     def display(self, reporter: Reporter):
#         reporter.positioned_error("Type Checking Error", self.msg, self.pos)
#         if self.note is not None:
#             reporter.separate()
#             with reporter.indent():
#                 self.note.display(reporter)
#
#
# class DefinitionNote(AizeMessage):
#     def __init__(self, source_name: str, pos: Position, msg: str):
#         super().__init__(self.NOTE)
#
#         self.source = source_name
#         self.pos = pos
#         self.msg = msg
#
#     @classmethod
#     def from_node(cls, node: Node, msg: str):
#         pos = Position.of(node)
#         return cls(pos.get_source_name(), pos, msg)
#
#     def display(self, reporter: Reporter):
#         reporter.positioned_error("Note", self.msg, self.pos)
# endregion


class BuiltinsCreator:
    def __init__(self, namespace: NamespaceSymbol):
        self.namespace = namespace

    def create_pos(self, name: str):
        return Position.new_builtin(name)

    def create_type(self, name: str):
        type_symbol = TypeSymbol(name, self.create_pos(name))
        self.namespace.define_type(type_symbol)
        return type_symbol

    def create_int_type(self, name: str, bit_size: int):
        int_type_symbol = IntTypeSymbol(name, bit_size, self.create_pos(name))
        self.namespace.define_type(int_type_symbol)
        return int_type_symbol

    @classmethod
    def add_builtins(cls, namespace: NamespaceSymbol):
        creator = cls(namespace)
        creator.create_int_type("int", bit_size=32)

        # returned instead of an actual type whenever an inconsistency in types occurs
        creator.create_type("<type check error>")


class CreateIR(ASTVisitor):
    @classmethod
    def create_ir(cls, program: ProgramAST) -> ProgramIR:
        return cls(program).visit_program(program)

    def visit_program(self, program: ProgramAST) -> ProgramIR:
        return ProgramIR([self.visit_source(source) for source in program.sources], NoNamespaceSymbol())

    def visit_source(self, source: SourceAST):
        return SourceIR([self.visit_top_level(top_level) for top_level in source.top_levels], NoNamespaceSymbol())

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
        return ParamIR(param.name, ann.type, param.pos)

    def visit_return(self, ret: ReturnStmtAST):
        return ReturnIR(self.visit_expr(ret.value), ret.pos)

    def visit_int(self, num: IntLiteralAST):
        return IntIR(num.num, num.pos)

    def visit_ann(self, ann: ExprAST):
        return AnnotationIR(self.visit_type(ann), ann.pos)

    def handle_malformed_type(self, type: ExprAST):
        # TODO
        return MalformedTypeIR(type.pos)

    def visit_get_type(self, type: GetVarExprAST):
        return GetTypeIR(type.var, type.pos)


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
        else:
            raise TypeError(f"Expected a expr node, got {expr}")

    @abstractmethod
    def visit_int(self, num: IntIR):
        pass

    @abstractmethod
    def visit_ann(self, ann: AnnotationIR):
        pass

    def visit_type(self, type: TypeIR):
        if isinstance(type, GetVarExprAST):
            return self.visit_get_type(type)
        else:
            raise TypeError(f"Expected a type node, got {type}")

    @abstractmethod
    def visit_get_type(self, type: GetVarExprAST):
        pass


class PassRegister:
    _instance_ = None

    def __init__(self):
        self._passes: Dict[str, Type[IRPass]] = {}

    @classmethod
    def _instance(cls):
        if cls._instance_ is None:
            cls._instance_ = cls()
        return cls._instance_

    @classmethod
    def register(cls, pass_: Type[IRPass]):
        inst = cls._instance()
        inst._passes[pass_.NAME] = pass_
        return pass_

    @classmethod
    def get_pass(cls, name: str) -> Type[IRPass]:
        return cls._instance()._passes[name]


class IRPass(IRVisitor):
    NAME: str
    PREREQUISITES: Set[str]

    def __init__(self):
        self.table = SymbolTable()

    @classmethod
    def apply_pass(cls, ir: ProgramIR):
        pass_ = cls()
        pass_.visit_program(ir)

    def enter_node(self, node: WithNamespace):
        return self.table.enter(node.namespace)

    def visit_program(self, program: ProgramIR):
        with self.enter_node(program):
            for source in program.sources:
                self.visit_source(source)

    def visit_source(self, source: SourceIR):
        with self.enter_node(source):
            for top_level in source.top_levels:
                self.visit_top_level(top_level)

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

    def visit_int(self, num: IntIR):
        pass

    def visit_ann(self, ann: AnnotationIR):
        pass

    def visit_get_type(self, type: GetVarExprAST):
        pass


@PassRegister.register
class CreateBuiltins(IRPass):
    NAME = 'CreateBuiltins'
    PREREQUISITES = set()

    def visit_program(self, program: ProgramIR):
        builtin_namespace = NamespaceSymbol("<builtins>", Position.new_none())
        BuiltinsCreator.add_builtins(builtin_namespace)

        program.namespace = builtin_namespace
