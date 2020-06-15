from __future__ import annotations

from abc import ABCMeta

from aizec.common import *

from aizec.aize_ir import *


E = TypeVar('E', bound=Extension)


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
        elif isinstance(stmt, IfStmtIR):
            return self.visit_if(stmt)
        elif isinstance(stmt, BlockIR):
            return self.visit_block(stmt)
        elif isinstance(stmt, VarDeclIR):
            return self.visit_var_decl(stmt)
        elif isinstance(stmt, ExprStmtIR):
            return self.visit_expr_stmt(stmt)
        else:
            raise TypeError(f"Expected a stmt node, got {stmt}")

    @abstractmethod
    def visit_if(self, if_: IfStmtIR):
        pass

    @abstractmethod
    def visit_var_decl(self, decl: VarDeclIR):
        pass

    @abstractmethod
    def visit_block(self, block: BlockIR):
        pass

    @abstractmethod
    def visit_expr_stmt(self, stmt: ExprStmtIR):
        pass

    @abstractmethod
    def visit_return(self, ret: ReturnIR):
        pass

    def visit_expr(self, expr: ExprIR):
        if isinstance(expr, IntIR):
            return self.visit_int(expr)
        elif isinstance(expr, CallIR):
            return self.visit_call(expr)
        elif isinstance(expr, GetVarIR):
            return self.visit_get_var(expr)
        elif isinstance(expr, SetVarIR):
            return self.visit_set_var(expr)
        elif isinstance(expr, CompareIR):
            return self.visit_compare(expr)
        elif isinstance(expr, ArithmeticIR):
            return self.visit_arithmetic(expr)
        else:
            raise TypeError(f"Expected a expr node, got {expr}")

    @abstractmethod
    def visit_compare(self, cmp: CompareIR):
        pass

    @abstractmethod
    def visit_arithmetic(self, arith: ArithmeticIR):
        pass

    @abstractmethod
    def visit_call(self, call: CallIR):
        pass

    @abstractmethod
    def visit_get_var(self, get_var: GetVarIR):
        pass

    @abstractmethod
    def visit_set_var(self, set_var: SetVarIR):
        pass

    @abstractmethod
    def visit_int(self, num: IntIR):
        pass

    @abstractmethod
    def visit_ann(self, ann: AnnotationIR):
        pass

    def visit_type(self, type: TypeIR):
        if isinstance(type, GetTypeIR):
            return self.visit_get_type(type)
        else:
            raise TypeError(f"Expected a type node, got {type}")

    @abstractmethod
    def visit_get_type(self, type: GetTypeIR):
        pass


class IRPass(ABC):
    def __init__(self, name: str):
        self.name: str = name

    @abstractmethod
    def can_run(self, ir: IR) -> bool:
        pass

    @abstractmethod
    def run_pass(self, ir: IR):
        pass


# region Metaclass Magic
class IRPassMetaclass(IRPass, ABC, ABCMeta):
    pass


class IRPassClass:
    __metaclass__ = IRPassMetaclass

    name: str

    def __init_subclass__(cls):
        cls.name = cls.get_name()

    @classmethod
    def get_name(cls) -> str:
        return cls.__name__

    @classmethod
    @abstractmethod
    def can_run(cls, ir: IR) -> bool:
        pass

    @classmethod
    @abstractmethod
    def run_pass(cls, ir: IR):
        pass
# endregion


class IRTreePass(IRVisitor, IRPassClass, ABC):
    def __init__(self, ir: IR):
        self.ir = ir

    @classmethod
    def run_pass(cls, ir: IR):
        pass_class = cls(ir)
        pass_class.visit_program(ir.program)

        if pass_class.was_successful():
            ir.ran_passes.add(cls)

    @abstractmethod
    def was_successful(self) -> bool:
        pass

    @classmethod
    def can_run(cls, ir: IR) -> bool:
        if ir.ran_passes.issuperset(cls.get_required_passes()) \
                and set(ir.extensions.keys()).issuperset(cls.get_required_extensions()):
            return True
        else:
            return False

    @classmethod
    @abstractmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        pass

    @classmethod
    @abstractmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        pass

    def add_ext(self, ext_type: Type[E]) -> E:
        ext_type: Type[Extension]
        ext = ext_type.new()
        self.ir.extensions[ext_type] = ext
        return ext

    def has_ext(self, ext_type: Type[E]) -> bool:
        return ext_type in self.ir.extensions

    def get_ext(self, ext_type: Type[E]) -> E:
        try:
            return self.ir.extensions[ext_type]
        except KeyError:
            raise ValueError(f"Extension {ext_type} has not been added to the ir yet. Specify that requirement.")

    def visit_program(self, program: ProgramIR):
        pass

    def visit_source(self, source: SourceIR):
        pass

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

    def visit_var_decl(self, decl: VarDeclIR):
        pass

    def visit_if(self, if_: IfStmtIR):
        pass

    def visit_block(self, block: BlockIR):
        pass

    def visit_return(self, ret: ReturnIR):
        pass

    def visit_expr_stmt(self, stmt: ExprStmtIR):
        pass

    def visit_call(self, call: CallIR):
        pass

    def visit_compare(self, cmp: CompareIR):
        pass

    def visit_arithmetic(self, arith: ArithmeticIR):
        pass

    def visit_get_var(self, get_var: GetVarIR):
        pass

    def visit_set_var(self, set_var: SetVarIR):
        pass

    def visit_int(self, num: IntIR):
        pass

    def visit_ann(self, ann: AnnotationIR):
        pass

    def visit_get_type(self, type: GetTypeIR):
        pass


class IRPassSequence(IRPass):
    def __init__(self, name: str, passes: List[IRPass] = None):
        super().__init__(name)
        self.passes: List[IRPass] = [] if passes is None else passes

    def can_run(self, ir: IR) -> bool:
        return any(ir_pass.can_run(ir) for ir_pass in self.passes)

    def add_pass(self, ir_pass: IRPass):
        self.passes.append(ir_pass)
        return ir_pass

    def run_pass(self, ir: IR):
        scheduler = PassScheduler(ir, self.passes.copy())
        scheduler.run_scheduled()
        ir.ran_passes.add(self)


PassAlias = Union[IRPass, Type[IRTreePass]]


class PassesRegister:
    _instance_ = None

    def __init__(self):
        self._passes: Dict[str, IRPass] = {}

    @classmethod
    def _instance(cls):
        if cls._instance_ is None:
            cls._instance_ = cls()
        return cls._instance_

    @classmethod
    @overload
    def register(cls, pass_: IRPass, *, to_sequences: Iterable[str] = None) -> IRPass:
        pass

    @classmethod
    @overload
    def register(cls, *, to_sequences: Iterable[str] = None) -> Callable[[IRPass], IRPass]:
        pass

    @classmethod
    def register(cls, pass_: IRPass = None, *, to_sequences: Iterable[PassAlias] = None):
        inst = cls._instance()
        if to_sequences is None:
            to_sequences = []
        to_sequences = set(to_sequences)

        def _register(ir_pass: IRPass):
            for seq in to_sequences:
                if isinstance(seq, IRPassSequence):
                    seq.add_pass(ir_pass)
                else:
                    raise ValueError(f"{seq.name} not a IRPassSequence")
            inst._passes[ir_pass.name] = ir_pass
            return ir_pass

        if pass_ is None:
            return _register
        else:
            return _register(pass_)

    @classmethod
    def get_pass(cls, name: str) -> IRPass:
        return cls._instance()._passes[name]


class PassScheduler:
    def __init__(self, ir: IR, scheduled_passes: List[PassAlias]):
        self.ir = ir
        self.scheduled_passes: List[PassAlias] = scheduled_passes

    def schedule(self, ir_pass: PassAlias) -> bool:
        if ir_pass in self.scheduled_passes:
            return False
        else:
            self.scheduled_passes.append(ir_pass)
            return True

    def run_scheduled(self):
        while len(self.scheduled_passes) > 0:
            for i in range(len(self.scheduled_passes)):
                ir_pass = self.scheduled_passes[i]
                if ir_pass.can_run(self.ir):
                    ir_pass.run_pass(self.ir)
                    self.scheduled_passes.pop(i)
                    break
            else:
                raise ValueError("No passes can be run due to their requirements.")
