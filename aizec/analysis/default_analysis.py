from __future__ import annotations

from aizec.common import *
from aizec.aize_common import AizeMessage, Reporter, MessageHandler, ErrorLevel, Position

from aizec.ir import IR, Extension
from aizec.ir.nodes import *
from aizec.ir_pass import IRTreePass, IRPassSequence, PassesRegister, PassAlias

from .symbol_data import SymbolData
from .symbols import *


T = TypeVar('T')


# region Errors
# TODO Errors could be unified into one class with multiple constructors
class DefinitionError(AizeMessage):
    def __init__(self, msg: str, pos: Position, notes: List[AizeMessage]):
        super().__init__(ErrorLevel.ERROR)
        self.msg = msg
        self.pos = pos
        self.notes = notes

    @classmethod
    def name_existing(cls, pos: Position, existing: Symbol = None):
        if existing:
            notes = [DefinitionNote.from_pos(existing.position, "Previously declared here")]
        else:
            notes = []
        error = cls(f"Name '{existing.name}' already declared in this scope", pos, notes)
        return error

    @classmethod
    def name_undefined(cls, pos: Position, name: str):
        error = cls(f"Name '{name}' could not be found", pos, [])
        return error

    @classmethod
    def attr_not_found(cls, attr_name: str, name: str, accessor: Position, agg_type: AggTypeSymbol):
        note = DefinitionNote.from_pos(agg_type.position, f"{agg_type} defined here")
        error = cls(f"{attr_name} '{name}' not found on {agg_type}", accessor, [])
        return error

    @classmethod
    def attr_repeated(cls, attr_name: str, repeat: Position, original: Position, name: str):
        note = DefinitionNote.from_pos(original, "Previously declared here")
        error = cls(f"{attr_name} name '{name}' repeated", repeat, [note])
        return error

    @classmethod
    def no_such_intrinsic(cls, intrinsic: Position, name: str):
        error = cls(f"No intrinsic with name '{name}'", intrinsic, [])
        return error

    def display(self, reporter: Reporter):
        reporter.positioned_error("Name Resolution Error", self.msg, self.pos)
        for note in self.notes:
            reporter.separate()
            with reporter.indent():
                note.display(reporter)


class DefinitionNote(AizeMessage):
    def __init__(self, msg: str, pos: Position):
        super().__init__(ErrorLevel.NOTE)
        self.msg = msg
        self.pos = pos

    @classmethod
    def from_node(cls, node: TextIR, msg: str):
        return cls.from_pos(node.pos, msg)

    @classmethod
    def from_pos(cls, pos: Position, msg: str):
        return cls(msg, pos)

    def display(self, reporter: Reporter):
        reporter.positioned_error("Note", self.msg, self.pos)


class TypeCheckingError(AizeMessage):
    def __init__(self, msg: str, pos: Position, notes: List[AizeMessage] = None):
        super().__init__(ErrorLevel.ERROR)
        self.pos = pos
        self.msg = msg

        self.notes = [] if notes is None else notes

    @classmethod
    def too_many_arguments(cls, expected_args: int, got_args: int, first_excess: Position):
        if expected_args == 1:
            error = cls(f"Expected {expected_args} argument, but got {got_args-expected_args} extra", first_excess)
        else:
            error = cls(f"Expected {expected_args} arguments, but got {got_args-expected_args} extra", first_excess)
        return error

    @classmethod
    def too_few_arguments(cls, expected_args: int, got_args: int, call: Position):
        if expected_args == 1:
            error = cls(f"Expected {expected_args} argument, but got {expected_args-got_args} too few", call)
        else:
            error = cls(f"Expected {expected_args} arguments, but got {expected_args-got_args} too few", call)
        return error

    @classmethod
    def expected_type(cls, expected: TypeSymbol, got: TypeSymbol, where: Position, declaration: Position = None):
        if declaration:
            notes = [DefinitionNote(f"Expected type declared here", declaration)]
        else:
            notes = []
        error = cls(f"Expected type {expected}, got type {got}", where, notes)
        return error

    @classmethod
    def expected_lval(cls, pos: Position):
        error = cls(f"Expected a place to store to, such as a variable or a field", pos)
        return error

    def display(self, reporter: Reporter):
        reporter.positioned_error("Type Checking Error", self.msg, self.pos)
        for note in self.notes:
            reporter.separate()
            with reporter.indent():
                note.display(reporter)


class FlowError(AizeMessage):
    def __init__(self, msg: str, pos: Position):
        super().__init__(ErrorLevel.ERROR)
        self.msg = msg
        self.pos = pos

    def display(self, reporter: Reporter):
        reporter.positioned_error("Control Flow Error", self.msg, self.pos)


class MalformedASTError(AizeMessage):
    def __init__(self, msg: str, pos: Position):
        super().__init__(ErrorLevel.ERROR)
        self.msg = msg
        self.pos = pos

    def display(self, reporter: Reporter):
        reporter.positioned_error("AST Conversion Error", self.msg, self.pos)
# endregion


DefaultPasses = IRPassSequence("DefaultPasses")
PassesRegister.register(DefaultPasses)


class LiteralData(Extension):
    class BuiltinData:
        def __init__(self, uint: Dict[int, TypeSymbol], sint: Dict[int, TypeSymbol]):
            self.uint = uint
            self.sint = sint

    def general(self, set_to: BuiltinData = None) -> BuiltinData:
        return super().general(set_to)


class TypeUnifier:
    def __init__(self, symbol_pass: IRSymbolsPass):
        self.symbols = symbol_pass.symbols

        TypeTuple: TypeAlias = Tuple[Type[TypeSymbol], Type[TypeSymbol]]
        UnifyFunc: TypeAlias = Callable[[ExprIR, TypeSymbol, TypeSymbol], ExprIR]
        # noinspection PyTypeChecker
        self.MAP: Dict[TypeTuple, UnifyFunc] = {
            (IntTypeSymbol, IntTypeSymbol): self.unify_int_int,
            (StructTypeSymbol, StructTypeSymbol): self.unify_struct_struct,
            (FunctionTypeSymbol, FunctionTypeSymbol): self.unify_func_func,
            (TupleTypeSymbol, TupleTypeSymbol): self.unify_tuple_tuple,
            (UnionVariantTypeSymbol, UnionTypeSymbol): self.unify_variant_union,
            (UnionTypeSymbol, UnionTypeSymbol): self.unify_union_union
        }

        self._node_ctx: Optional[TextIR] = None
        self._type_decl_ctx: Optional[Position] = None

    @contextmanager
    def _set_context(self, node: NodeIR, type_decl: Position):
        old_node, old_type = self._node_ctx, self._type_decl_ctx
        self._node_ctx, self._type_decl_ctx = node, type_decl
        yield
        self._node_ctx, self._type_decl_ctx = old_node, old_type

    def report_error(self, msg: str, show_decl: bool = False):
        if show_decl and self._type_decl_ctx is not None and not self._type_decl_ctx.is_none():
            notes = [DefinitionNote.from_pos(self._type_decl_ctx, "Expected type declared here")]
        else:
            notes = []
        msg = TypeCheckingError(msg, self.pos, notes)
        MessageHandler.handle_message(msg)

    def create_type_ir(self, type: TypeSymbol) -> TypeIR:
        gen = GeneratedTypeIR(self.pos)
        self.symbols.type(gen, set_to=SymbolData.TypeData(type))
        return gen

    @property
    def pos(self):
        return self._node_ctx.pos

    def unify_type(self, expr: ExprIR, to_type: TypeSymbol, node: TextIR, type_decl: Position = None) -> ExprIR:
        with self._set_context(node, type_decl):
            from_type = self.symbols.expr(expr).return_type
            if isinstance(from_type, ErroredTypeSymbol) or isinstance(to_type, ErroredTypeSymbol):
                return expr
            type_tuple = type(from_type), type(to_type)
            if type_tuple in self.MAP:
                return self.MAP[type_tuple](expr, from_type, to_type)
            else:
                self.report_error(f"Expected type {to_type}, got {from_type}", show_decl=True)
                return expr

    def unify_int_int(self, expr: ExprIR, from_type: IntTypeSymbol, to_type: IntTypeSymbol) -> ExprIR:
        from_bits, to_bits = from_type.bit_size, to_type.bit_size
        if from_type.is_signed != to_type.is_signed:
            self.report_error("Cannot mix signed and unsigned integers")
            return expr
        else:
            is_signed = from_type.is_signed
            if from_bits < to_bits:
                cast_type = self.create_type_ir(to_type)
                cast_expr = CastIntIR(expr, cast_type, self.pos)
                self.symbols.expr(cast_expr, set_to=SymbolData.ExprData(to_type, False))
                self.symbols.cast_int(cast_expr, set_to=SymbolData.CastIntData(from_bits, to_bits, is_signed))
                return cast_expr
            elif from_bits == to_bits:
                return expr
            else:
                self.report_error("Cannot implicitly reduce an integer's size")
                return expr

    def unify_struct_struct(self, expr: ExprIR, from_type: StructTypeSymbol, to_type: StructTypeSymbol) -> ExprIR:
        if from_type is to_type:
            return expr
        else:
            self.report_error(f"Expected type {to_type}, got {from_type}", show_decl=True)
            return expr

    def unify_func_func(self, expr: ExprIR, from_type: FunctionTypeSymbol, to_type: FunctionTypeSymbol) -> ExprIR:
        if from_type is to_type:
            return expr
        else:
            self.report_error(f"Expected type {to_type}, got {from_type}", show_decl=True)
            return expr

    def unify_tuple_tuple(self, expr: ExprIR, from_type: FunctionTypeSymbol, to_type: FunctionTypeSymbol) -> ExprIR:
        if from_type is to_type:
            return expr
        else:
            self.report_error(f"Expected type {to_type}, got {from_type}", show_decl=True)
            return expr

    def unify_variant_union(self, expr: ExprIR, from_type: UnionVariantTypeSymbol, to_type: UnionTypeSymbol) -> ExprIR:
        if from_type.union is to_type:
            union_ir = self.create_type_ir(to_type)
            variant_ir = self.create_type_ir(from_type)
            cast_expr = CastUnionIR(expr, union_ir, variant_ir, expr.pos)
            self.symbols.cast_union(cast_expr, set_to=SymbolData.CastUnionData(from_type, to_type))
            self.symbols.expr(cast_expr, set_to=SymbolData.ExprData(to_type, False))
            return cast_expr
        else:
            self.report_error(f"Cannot cast since {to_type} is not {from_type}'s parent")
            return expr

    def unify_union_union(self, expr: ExprIR, from_type: UnionTypeSymbol, to_type: UnionTypeSymbol) -> ExprIR:
        if from_type is to_type:
            return expr
        else:
            self.report_error(f"Expected type {to_type}, got {from_type}", show_decl=True)
            return expr


class IRSymbolsPass(IRTreePass, ABC):
    def __init__(self, ir: IR):
        super().__init__(ir)
        self._table = SymbolTable()

        self.symbols = self.get_ext(SymbolData)
        self._unifier = TypeUnifier(self)

    def was_successful(self) -> bool:
        MessageHandler.flush_messages()
        return True

    def enter_namespace(self, namespace: NamespaceSymbol):
        if namespace.namespace is not None:
            if namespace.namespace is not self.current_namespace:
                raise ValueError("When entering a namespace, it must be a child of the current namespace")
        return self._table.enter(namespace)

    @property
    def current_namespace(self) -> NamespaceSymbol:
        return self._table.current_namespace

    # region Type Checking Utils
    def _lookup(self, type: str, name: str, node: TextIR, ns: NamespaceSymbol = None):
        if ns is None:
            ns = self.current_namespace
        err_cls = {"type": ErroredTypeSymbol, "value": ErroredVariableSymbol, "namespace": ErroredNamespaceSymbol}[type]
        try:
            # noinspection PyArgumentList
            resolved_symbol = ns.lookup(type, name)
        except FailedLookupError as err:
            msg = DefinitionError.name_undefined(node.pos, err.failed_name)
            MessageHandler.handle_message(msg)
            resolved_symbol = err_cls(node, node.pos)
        return resolved_symbol

    def lookup_type(self, name: str, node: TextIR, in_namespace: NamespaceSymbol = None) -> TypeSymbol:
        return self._lookup("type", name, node, in_namespace)

    def lookup_value(self, name: str, node: TextIR, in_namespace: NamespaceSymbol = None) -> VariableSymbol:
        return self._lookup("value", name, node, in_namespace)

    def lookup_namespace(self, name: str, node: TextIR, in_namespace: NamespaceSymbol = None) -> NamespaceSymbol:
        return self._lookup("namespace", name, node, in_namespace)

    def define_value(self, symbol: VariableSymbol, in_namespace: NamespaceSymbol = None):
        if in_namespace is None:
            in_namespace = self.current_namespace
        try:
            in_namespace.define_value(symbol)
        except DuplicateSymbolError as err:
            msg = DefinitionError.name_existing(symbol.position, err.old_symbol)
            MessageHandler.handle_message(msg)
    # endregion

    def typeof(self, node: Union[TypeIR, ExprIR]) -> TypeSymbol:
        return self.symbols.type(node).resolved_type if isinstance(node, TypeIR) else self.symbols.expr(node).return_type

    def create_function(self, func: Union[AggFuncIR, FunctionIR, LambdaIR]):
        name = "<lambda>" if isinstance(func, LambdaIR) else func.name
        func.params = [self.visit_param(param) for param in func.params]
        func.ret = self.visit_type(func.ret)
        func_type = FunctionTypeSymbol([self.typeof(param.type) for param in func.params], self.typeof(func.ret), func, func.pos)
        func_value = VariableSymbol(name, func, func_type, func.pos)
        func_namespace = NamespaceSymbol(f"function {name}", func, func.pos)
        self.current_namespace.define_namespace(func_namespace, visible=False)
        self.symbols.decl(func, set_to=SymbolData.DeclData(func, func_value, func_type))
        return func_value, func_namespace

    def visit_param(self, param: ParamIR):
        param.type = self.visit_type(param.type)
        symbol = VariableSymbol(param.name, param, self.typeof(param.type), param.pos)
        self.symbols.param(param, set_to=SymbolData.ParamData(symbol))
        return param

    def visit_tuple_type(self, type: TupleTypeIR):
        type.items = [self.visit_type(item) for item in type.items]
        resolved_type = TupleTypeSymbol([self.typeof(item) for item in type.items], type, type.pos)
        self.symbols.type(type, set_to=SymbolData.TypeData(resolved_type))
        return type

    def visit_func_type(self, type: FuncTypeIR):
        type.params = [self.visit_type(param_type) for param_type in type.params]
        type.ret = self.visit_type(type.ret)
        resolved_type = FunctionTypeSymbol([self.typeof(param_type) for param_type in type.params], self.typeof(type.ret), type, type.pos)
        self.symbols.type(type, SymbolData.TypeData(resolved_type))
        return type

    def visit_get_type(self, type: GetTypeIR):
        resolved_type = self.lookup_type(type.name, type)
        self.symbols.type(type, SymbolData.TypeData(resolved_type))
        return type

    def visit_no_type(self, type: NoTypeIR):
        return type


@PassesRegister.register(to_sequences=[DefaultPasses])
class InitSymbols(IRSymbolsPass):
    def __init__(self, ir: IR):
        self.ir = ir
        self.symbols: SymbolData = self.add_ext(SymbolData)
        self.builtins: LiteralData = self.add_ext(LiteralData)
        super().__init__(ir)

    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return set()

    @classmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        return set()

    def visit_program(self, program: ProgramIR):
        builtin_namespace = NamespaceSymbol("program", program, Position.new_none())
        self.symbols.program(program, set_to=SymbolData.ProgramData(builtin_namespace))

        def def_int(name, signed, bits):
            i = IntTypeSymbol(name, signed, bits, program, Position.new_none())
            builtin_namespace.define_type(i)
            return i

        uint1 = def_int("bool", False, 1)
        uint8 = def_int("uint8", False, 8)
        uint32 = def_int("uint32", False, 32)
        uint64 = def_int("uint64", False, 64)

        int8 = def_int("int8", True, 8)
        int32 = def_int("int32", True, 32)
        int64 = def_int("int64", True, 64)

        self.builtins.general(set_to=LiteralData.BuiltinData({1: uint1, 8: uint8, 32: uint32, 64: uint64},
                                                             {8: int8, 32: int32, 64: int64}))

        with self.enter_namespace(builtin_namespace):
            for source in program.sources:
                self.visit_source(source)

    def visit_source(self, source: SourceIR):
        global_namespace = NamespaceSymbol(f"source {source.source_name}", source, Position.new_source(source.source_name))
        self.current_namespace.define_namespace(global_namespace, visible=False)
        self.symbols.source(source, set_to=SymbolData.SourceData(global_namespace))


@PassesRegister.register(to_sequences=[DefaultPasses])
class DeclareTypes(IRSymbolsPass):
    def __init__(self, ir: IR):
        super().__init__(ir)

        self.builtins: LiteralData = self.get_ext(LiteralData)

    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return {InitSymbols}

    @classmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        return {LiteralData, SymbolData}

    def visit_program(self, program: ProgramIR):
        with self.enter_namespace(self.symbols.program(program).builtins):
            for source in program.sources:
                self.visit_source(source)

    def visit_source(self, source: SourceIR):
        with self.enter_namespace(self.symbols.source(source).globals):
            for top_level in source.top_levels:
                self.visit_top_level(top_level)

    def visit_import(self, imp: ImportIR):
        source = imp.source_ir
        namespace = self.symbols.source(source).globals

        raw_name = imp.path.with_suffix("").name
        fixed_name = raw_name.replace(" ", "_")
        if not fixed_name.isidentifier():
            # TODO
            raise Exception(raw_name)

        try:
            self.current_namespace.define_namespace(namespace, as_name=fixed_name, is_parent=False)
        except DuplicateSymbolError as err:
            msg = DefinitionError.name_existing(imp.pos, err.old_symbol)
            MessageHandler.handle_message(msg)

    def visit_union(self, union: UnionIR):
        variants: Dict[str, Tuple[TypeSymbol, Position]] = {}
        for variant in union.variants:
            if variant.name in variants:
                msg = DefinitionError.attr_repeated("Variant", variant.pos, variants[variant.name][1], variant.name)
                MessageHandler.handle_message(msg)
            else:
                variant.contains = self.visit_type(variant.contains)
                variants[variant.name] = self.symbols.type(variant.contains).resolved_type, variant.pos
        union_type = UnionTypeSymbol(union.name, variants, {}, {}, union, union.pos)
        self.current_namespace.define_type(union_type)

        index = 0
        for variant_name, (variant_type, variant_pos) in variants.items():
            variant_type = UnionVariantTypeSymbol(variant_name, variant_name, index, variant_type, union_type, union, variant_pos)
            union_type.variant_types[variant_name] = variant_type
            self.current_namespace.define_type(variant_type)
            index += 1

        self.symbols.union(union, set_to=SymbolData.UnionData(union_type))

    def visit_struct(self, struct: StructIR):
        fields: Dict[str, Tuple[TypeSymbol, Position]] = {}
        for field in struct.fields:
            if field.name in fields:
                msg = DefinitionError.attr_repeated("field", field.pos, fields[field.name][1], field.name)
                MessageHandler.handle_message(msg)
            else:
                field.type = self.visit_type(field.type)
                fields[field.name] = self.symbols.type(field.type).resolved_type, field.pos
        struct_type = StructTypeSymbol(struct.name, fields, {}, struct, struct.pos)
        self.current_namespace.define_type(struct_type)
        self.symbols.struct(struct, set_to=SymbolData.StructData(struct_type))


@PassesRegister.register(to_sequences=[DefaultPasses])
class DeclareFunctions(IRSymbolsPass):
    def __init__(self, ir: IR):
        super().__init__(ir)

        self.builtins: LiteralData = self.get_ext(LiteralData)

        self.current_agg: Optional[AggTypeSymbol] = None

    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return {InitSymbols, DeclareTypes}

    @classmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        return {LiteralData, SymbolData}

    @contextmanager
    def in_agg(self, type: AggTypeSymbol):
        old, self.current_agg = self.current_agg, type
        yield
        self.current_agg = old

    def visit_program(self, program: ProgramIR):
        with self.enter_namespace(self.symbols.program(program).builtins):
            for source in program.sources:
                self.visit_source(source)

    def visit_source(self, source: SourceIR):
        with self.enter_namespace(self.symbols.source(source).globals):
            for top_level in source.top_levels:
                self.visit_top_level(top_level)

    def visit_union(self, union: UnionIR):
        union_type = self.symbols.union(union).union_type
        funcs: Dict[str, VariableSymbol] = {}
        for func in union.funcs:
            if func.name in union_type.variants:
                msg = DefinitionError.attr_repeated("field", func.pos, union_type.variants[func.name][1], func.name)
                MessageHandler.handle_message(msg)
            elif func.name in funcs:
                msg = DefinitionError.name_existing(func.pos, funcs[func.name])
                MessageHandler.handle_message(msg)
            else:
                with self.in_agg(union_type):
                    self.visit_agg_func(func)
                    funcs[func.name] = self.symbols.decl(func).declares
        union_type.funcs = funcs

    def visit_struct(self, struct: StructIR):
        struct_type = self.symbols.struct(struct).struct_type
        funcs: Dict[str, VariableSymbol] = {}
        for func in struct.funcs:
            if func.name in struct_type.fields:
                msg = DefinitionError.attr_repeated("field", func.pos, struct_type.fields[func.name][1], func.name)
                MessageHandler.handle_message(msg)
            elif func.name in funcs:
                msg = DefinitionError.name_existing(func.pos, funcs[func.name])
                MessageHandler.handle_message(msg)
            else:
                with self.in_agg(struct_type):
                    self.visit_agg_func(func)
                    funcs[func.name] = self.symbols.decl(func).declares
        struct_type.funcs = funcs

    def visit_agg_func(self, func: AggFuncIR):
        if len(func.params) < 1:
            msg = TypeCheckingError(f"Expected at least 1 parameter (self)", func.pos)
            MessageHandler.handle_message(msg)
        else:
            self_param = func.params[0]
            self.symbols.type(self_param.type, set_to=SymbolData.TypeData(self.current_agg))

        func_value, func_namespace = self.create_function(func)
        self.symbols.agg_func(func, set_to=SymbolData.AggFuncData(func_value, func_namespace))

    def visit_function(self, func: FunctionIR):
        func_value, func_namespace = self.create_function(func)

        try:
            self.current_namespace.define_value(func_value)
        except DuplicateSymbolError as err:
            msg = DefinitionError.name_existing(func.pos, err.old_symbol)
            MessageHandler.handle_message(msg)

        attrs = [attr.name for attr in func.attrs]
        self.symbols.function(func, set_to=SymbolData.FunctionData(func_value, func_namespace, attrs))


@PassesRegister.register(to_sequences=[DefaultPasses])
class ResolveSymbols(IRSymbolsPass):
    def __init__(self, ir: IR):
        super().__init__(ir)
        self._current_func: Optional[Union[FunctionIR, AggFuncIR]] = None
        self._current_func_type: Optional[FunctionTypeSymbol] = None

        self.builtins: LiteralData = self.get_ext(LiteralData)

    # region Pass Info
    @classmethod
    def get_required_passes(cls) -> Set[PassAlias]:
        return {InitSymbols, DeclareTypes, DeclareFunctions}

    @classmethod
    def get_required_extensions(cls) -> Set[Type[Extension]]:
        return {LiteralData, SymbolData}
    # endregion

    # region Current Function Utils
    @property
    def current_func(self):
        if self._current_func is not None:
            return self._current_func
        else:
            raise ValueError("Not in a function")

    @property
    def current_func_type(self):
        if self._current_func_type is not None:
            return self._current_func_type
        else:
            raise ValueError("Not in a function")

    @contextmanager
    def in_function(self, func: Union[FunctionIR, AggFuncIR, LambdaIR], type: FunctionTypeSymbol):
        old_func, self._current_func = self._current_func, func
        old_type, self._current_func_type = self._current_func_type, type
        if isinstance(func, FunctionIR):
            namespace = self.symbols.function(func).namespace
        else:
            namespace = self.symbols.agg_func(func).namespace
        with self.enter_namespace(namespace):
            yield
        self._current_func = old_func
        self._current_func_type = old_type
    # endregion

    def visit_program(self, program: ProgramIR):
        with self.enter_namespace(self.symbols.program(program).builtins):
            for source in program.sources:
                self.visit_source(source)

    def visit_source(self, source: SourceIR):
        with self.enter_namespace(self.symbols.source(source).globals):
            for top_level in source.top_levels:
                self.visit_top_level(top_level)

    def visit_union(self, union: UnionIR):
        for func in union.funcs:
            self.visit_agg_func(func)

    def visit_struct(self, struct: StructIR):
        for func in struct.funcs:
            self.visit_agg_func(func)

    def visit_agg_func(self, func: AggFuncIR):
        data = self.symbols.agg_func(func)
        func_type = cast(FunctionTypeSymbol, data.symbol.type)
        func_namespace = data.namespace

        with self.in_function(func, func_type):
            for param in func.params:
                param_symbol = self.symbols.param(param).symbol

                self.define_value(param_symbol, in_namespace=func_namespace)

        is_terminated = False
        with self.in_function(func, func_type):
            for stmt in func.body:
                self.visit_stmt(stmt)
                stmt_terminates = self.symbols.stmt(stmt).is_terminal
                if stmt_terminates:
                    if not is_terminated:
                        is_terminated = True
                    else:
                        # TODO Error
                        is_terminated = True
        # TODO if return is void or (), then it does not need to be terminated
        if not is_terminated:
            msg = FlowError("Function ends without always terminating", func.pos)
            MessageHandler.handle_message(msg)

    def visit_function(self, func: FunctionIR):
        data = self.symbols.function(func)
        func_type = cast(FunctionTypeSymbol, data.symbol.type)
        func_namespace = data.namespace

        with self.in_function(func, func_type):
            for param in func.params:
                param_symbol = self.symbols.param(param).symbol
                self.define_value(param_symbol, in_namespace=func_namespace)

        is_terminated = False
        with self.in_function(func, func_type):
            for stmt in func.body:
                self.visit_stmt(stmt)
                stmt_terminates = self.symbols.stmt(stmt).is_terminal
                if stmt_terminates:
                    if not is_terminated:
                        is_terminated = True
                    else:
                        # TODO Error
                        is_terminated = True
        # TODO if return is void or (), then it does not need to be terminated
        if not is_terminated:
            msg = FlowError("Function ends without always terminating", func.pos)
            MessageHandler.handle_message(msg)

    def unify_type(self, expr: ExprIR, to_type: TypeSymbol, node: TextIR, type_decl: Position = None) -> ExprIR:
        return self._unifier.unify_type(expr, to_type, node, type_decl)

    def visit_if(self, if_: IfStmtIR):
        if_.cond = self.visit_expr(if_.cond)
        self.visit_stmt(if_.else_do)
        self.visit_stmt(if_.then_do)

        boolean = self.builtins.general().uint[1]
        if_.cond = self.unify_type(if_.cond, boolean, if_)

        is_terminal = self.symbols.stmt(if_.else_do).is_terminal and self.symbols.stmt(if_.then_do).is_terminal
        self.symbols.stmt(if_, set_to=SymbolData.StmtData(is_terminal))

    def visit_while(self, while_: WhileStmtIR):
        while_.cond = self.visit_expr(while_.cond)
        self.visit_stmt(while_.while_do)

        boolean = self.builtins.general().uint[1]
        while_.cond = self.unify_type(while_.cond, boolean, while_)

        is_terminal = self.symbols.stmt(while_.while_do).is_terminal
        self.symbols.stmt(while_, set_to=SymbolData.StmtData(is_terminal))

    def visit_expr_stmt(self, stmt: ExprStmtIR):
        stmt.expr = self.visit_expr(stmt.expr)
        self.symbols.stmt(stmt, set_to=SymbolData.StmtData(is_terminal=False))

    def visit_var_decl(self, decl: VarDeclIR):
        decl.ann = self.visit_ann(decl.ann)
        var_type = self.symbols.type(decl.ann.type).resolved_type

        decl.value = self.visit_expr(decl.value)
        value_type = self.symbols.expr(decl.value).return_type

        decl.value = self.unify_type(decl.value, var_type, decl)

        symbol = VariableSymbol(decl.name, decl, var_type, decl.pos)
        self.define_value(symbol)

        self.symbols.decl(decl, set_to=SymbolData.DeclData(decl, symbol, var_type))
        self.symbols.stmt(decl, set_to=SymbolData.StmtData(is_terminal=False))

    def visit_block(self, block: BlockIR):
        # TODO scope
        block_is_terminal = False
        for stmt in block.stmts:
            self.visit_stmt(stmt)
            stmt_is_terminal = self.symbols.stmt(stmt).is_terminal
            if stmt_is_terminal:
                if not block_is_terminal:
                    block_is_terminal = True
                else:
                    # TODO ERROR (multiple returns, unreachable)
                    block_is_terminal = True
        self.symbols.stmt(block, set_to=SymbolData.StmtData(block_is_terminal))

    def visit_return(self, ret: ReturnIR):
        ret.expr = self.visit_expr(ret.expr)
        expected = self.current_func_type.ret

        ret.expr = self.unify_type(ret.expr, expected, ret)

        self.symbols.stmt(ret, set_to=SymbolData.StmtData(True))

    def expect_type_cls(self, typed: Union[TypeIR, ExprIR], *types: Type[TypeSymbol]) -> Optional[ErroredTypeSymbol]:
        expr_type = self.typeof(typed)
        if isinstance(expr_type, types):
            return None
        elif isinstance(expr_type, ErroredTypeSymbol):
            return expr_type
        else:
            if len(types) == 1:
                msg = TypeCheckingError(f"Expected {types[0].get_cls_name()}, got {expr_type.get_cls_name()}", typed.pos)
            elif len(types) == 2:
                msg = TypeCheckingError(f"Expected {types[0].get_cls_name()} or {types[1].get_cls_name()}, got {expr_type.get_cls_name()}", typed.pos)
            else:
                s = ', '.join(type.get_cls_name() for type in types[:-1]) + ', or ' + types[-1].get_cls_name()
                msg = TypeCheckingError(f"Expected {s}, got {expr_type.get_cls_name()}", typed.pos)
            MessageHandler.handle_message(msg)
            return ErroredTypeSymbol(typed, typed.pos)

    def visit_is(self, is_: IsIR):
        is_.expr = self.visit_expr(is_.expr)

        union_type = None
        variant = None
        if errored_type := self.expect_type_cls(is_.expr, UnionTypeSymbol):
            return_type = errored_type
        else:
            union_type = cast(UnionTypeSymbol, self.typeof(is_.expr))
            if is_.variant in union_type.variants:
                variant = union_type.variant_types[is_.variant]
                contains = variant.contains
            else:
                msg = DefinitionError.attr_not_found("variant", is_.variant, is_.pos, union_type)
                MessageHandler.handle_message(msg)
                contains = ErroredTypeSymbol(is_, is_.pos)
            value_symbol = VariableSymbol(is_.to_var, is_, contains, is_.pos)
            self.define_value(value_symbol)
            return_type = self.builtins.general().uint[1]

        self.symbols.expr(is_, set_to=SymbolData.ExprData(return_type, False))
        self.symbols.is_(is_, set_to=SymbolData.IsData(union_type, variant))
        return is_

    def visit_compare(self, cmp: CompareIR):
        cmp.left = self.visit_expr(cmp.left)
        cmp.right = self.visit_expr(cmp.right)

        if errored_type := (self.expect_type_cls(cmp.left, IntTypeSymbol) or self.expect_type_cls(cmp.right, IntTypeSymbol)):
            return_type = errored_type
            is_signed = True
        else:
            left = cast(IntTypeSymbol, self.typeof(cmp.left))
            right = cast(IntTypeSymbol, self.typeof(cmp.right))
            is_signed = left.is_signed
            return_type = self.builtins.general().uint[1]
                
        self.symbols.expr(cmp, SymbolData.ExprData(return_type, False))
        self.symbols.compare(cmp, SymbolData.CompareData(is_signed))
        return cmp

    def visit_arithmetic(self, arith: ArithmeticIR):
        arith.left = self.visit_expr(arith.left)
        arith.right = self.visit_expr(arith.right)

        if errored_type := (self.expect_type_cls(arith.left, IntTypeSymbol) or self.expect_type_cls(arith.right, IntTypeSymbol)):
            return_type = errored_type
            is_signed = True
        else:
            left = cast(IntTypeSymbol, self.typeof(arith.left))
            right = cast(IntTypeSymbol, self.typeof(arith.right))
            is_signed = left.is_signed
            return_type = max(left, right, key=lambda t: t.bit_size)

        self.symbols.expr(arith, SymbolData.ExprData(return_type, False))
        self.symbols.arithmetic(arith, SymbolData.ArithmeticData(is_signed))
        return arith

    def visit_negate(self, negate: NegateIR):
        negate.right = self.visit_expr(negate.right)

        if errored_type := self.expect_type_cls(negate.right, IntTypeSymbol):
            return_type = errored_type
        else:
            right = cast(IntTypeSymbol, self.typeof(negate.right))
            return_type = right

        self.symbols.expr(negate, set_to=SymbolData.ExprData(return_type, False))
        return negate

    # def check_argument_count(self, arguments: List[ExprIR], expected_count: int, pos: Position) -> bool:
    #     got_count = len(arguments)
    #     if got_count > expected_count:
    #         excess = arguments[got_count - expected_count]
    #         msg = TypeCheckingError.too_many_arguments(expected_count, got_count, excess.pos)
    #         MessageHandler.handle_message(msg)
    #         return False
    #     elif got_count < expected_count:
    #         msg = TypeCheckingError.too_few_arguments(expected_count, got_count, pos)
    #         MessageHandler.handle_message(msg)
    #         return False
    #     else:
    #         return True

    def unify_arguments(self, args: List[ExprIR], params: List[TypeSymbol], node: TextIR) -> List[ExprIR]:
        if len(args) > len(params):
            excess = args[len(args) - len(params)]
            msg = TypeCheckingError.too_many_arguments(len(params), len(args), excess.pos)
            MessageHandler.handle_message(msg)
            # noinspection PyTypeChecker
            params = params + [None]*(len(args) - len(params))
        elif len(args) < len(params):
            msg = TypeCheckingError.too_few_arguments(len(params), len(args), node.pos)
            MessageHandler.handle_message(msg)
        new_args = []
        for arg, param in zip(args, params):
            if param is None:
                new_args.append(arg)
            else:
                new_args.append(self.unify_type(arg, param, node))
        return new_args

    def visit_new(self, new: NewIR):
        new.type = self.visit_type(new.type)
        new.arguments = [self.visit_expr(arg) for arg in new.arguments]

        if errored_type := self.expect_type_cls(new.type, StructTypeSymbol, UnionTypeSymbol):
            return_type = errored_type
        else:
            return_type = type = self.typeof(new.type)
            if isinstance(type, StructTypeSymbol):
                field_types = [field_type for _, (field_type, _) in type.fields.items()]
                new.arguments = self.unify_arguments(new.arguments, field_types, new)
            elif isinstance(type, UnionVariantTypeSymbol):
                new.arguments = self.unify_arguments(new.arguments, [type.contains], new)

        self.symbols.expr(new, set_to=SymbolData.ExprData(return_type, False))
        return new

    def visit_call(self, call: CallIR):
        call.callee = self.visit_expr(call.callee)
        call.arguments = [self.visit_expr(arg) for arg in call.arguments]

        if isinstance(call.callee, GetAttrIR) and self.symbols.get_attr(call.callee).is_method:
            func_value = self.symbols.get_attr(call.callee).func

            obj = call.callee.obj
            func_name = call.callee.attr
            args_with_obj = [obj] + call.arguments

            if errored_type := self.expect_type_cls(call.callee, FunctionTypeSymbol):
                return_type = errored_type
            else:
                func_type = cast(FunctionTypeSymbol, self.typeof(call.callee))
                return_type = func_type.ret
                args_with_obj = self.unify_arguments(args_with_obj, func_type.params, call)
                call.arguments = args_with_obj[1:]

            method_call = MethodCallIR(obj, func_name, call.arguments, call.pos)
            self.symbols.expr(method_call, set_to=SymbolData.ExprData(return_type, False))
            self.symbols.method_call(method_call, set_to=SymbolData.MethodCallData(func_value))
            return method_call

        if errored_type := self.expect_type_cls(call.callee, FunctionTypeSymbol):
            return_type = errored_type
        else:
            func_type = cast(FunctionTypeSymbol, self.typeof(call.callee))
            return_type = func_type.ret
            call.arguments = self.unify_arguments(call.arguments, func_type.params, call)

        self.symbols.expr(call, SymbolData.ExprData(return_type, False))
        return call

    def visit_get_var(self, get_var: GetVarIR):
        variable = self.lookup_value(get_var.var_name, get_var)
        is_function = isinstance(variable.type, FunctionTypeSymbol)
        self.symbols.expr(get_var, SymbolData.ExprData(variable.type, is_lval=not is_function))
        self.symbols.get_var(get_var, set_to=SymbolData.GetVarData(variable, is_function))
        return get_var

    def visit_set_var(self, set_var: SetVarIR):
        set_var.value = self.visit_expr(set_var.value)

        variable = self.lookup_value(set_var.var_name, set_var)
        variable_type = variable.type

        value_type = self.symbols.expr(set_var.value).return_type

        set_var.value = self.unify_type(set_var.value, variable_type, set_var, variable.position)
        return_type = self.typeof(set_var.value)

        self.symbols.expr(set_var, set_to=SymbolData.ExprData(return_type, True))
        self.symbols.set_var(set_var, set_to=SymbolData.SetVarData(variable))
        return set_var

    def visit_get_attr(self, get_attr: GetAttrIR):
        get_attr.obj = self.visit_expr(get_attr.obj)
        obj_type = self.typeof(get_attr.obj)
        obj_is_lval = self.symbols.expr(get_attr.obj).is_lval

        return_type: TypeSymbol
        index: Optional[int] = None
        is_method: Optional[bool] = None
        func: Optional[VariableSymbol] = None
        if errored_type := self.expect_type_cls(get_attr.obj, AggTypeSymbol):
            return_type = errored_type
            agg_type = errored_type
        else:
            agg_type = cast(AggTypeSymbol, obj_type)
            if isinstance(agg_type, StructTypeSymbol) and get_attr.attr in agg_type.fields:
                return_type, _ = agg_type.fields[get_attr.attr]
                index = list(agg_type.fields.keys()).index(get_attr.attr)
            elif get_attr.attr in agg_type.funcs:
                func = agg_type.funcs[get_attr.attr]
                return_type = func.type
                is_method = True
            else:
                msg = DefinitionError.attr_not_found("field", get_attr.attr, get_attr.pos, agg_type)
                MessageHandler.handle_message(msg)
                return_type = ErroredTypeSymbol(get_attr, get_attr.pos)

        self.symbols.expr(get_attr, set_to=SymbolData.ExprData(return_type, is_lval=obj_is_lval))
        self.symbols.get_attr(get_attr, set_to=SymbolData.GetAttrData(agg_type, index, is_method, func))
        return get_attr

    def visit_set_attr(self, set_attr: SetAttrIR):
        set_attr.obj = self.visit_expr(set_attr.obj)
        obj_type = self.symbols.expr(set_attr.obj).return_type
        obj_is_lval = self.symbols.expr(set_attr.obj).is_lval

        set_attr.value = self.visit_expr(set_attr.value)
        value_type = self.symbols.expr(set_attr.value).return_type
        value_is_lval = self.symbols.expr(set_attr.value).is_lval

        return_type: TypeSymbol
        if errored_type := self.expect_type_cls(set_attr.obj, StructTypeSymbol):
            return_type = errored_type
            struct_type = None
            index = None
        else:
            struct_type = cast(StructTypeSymbol, obj_type)

            if set_attr.attr in struct_type.fields:
                field_type, field_pos = struct_type.fields[set_attr.attr]
                index = list(struct_type.fields.keys()).index(set_attr.attr)

                set_attr.value = self.unify_type(set_attr.value, field_type, set_attr)
                return_type = self.typeof(set_attr.value)
            else:
                msg = DefinitionError.attr_not_found("field", set_attr.attr, set_attr.pos, struct_type)
                MessageHandler.handle_message(msg)
                return_type = ErroredTypeSymbol(set_attr, set_attr.pos)
                index = None

        if not obj_is_lval:
            msg = TypeCheckingError.expected_lval(set_attr.obj.pos)
            MessageHandler.handle_message(msg)

        self.symbols.expr(set_attr, set_to=SymbolData.ExprData(return_type, is_lval=True))
        self.symbols.set_attr(set_attr, set_to=SymbolData.SetAttrData(struct_type, index))
        return set_attr

    def visit_intrinsic(self, intrinsic: IntrinsicIR):
        if intrinsic.name in ('int8', 'int32', 'int64'):
            to_bits = int(intrinsic.name[3:])

            intrinsic.args = [self.visit_expr(arg) for arg in intrinsic.args]
            expected = [self.builtins.general().sint[64]]
            intrinsic.args = self.unify_arguments(intrinsic.args, expected, intrinsic)
            return_type = self.builtins.general().sint[to_bits]

            self.symbols.expr(intrinsic, set_to=SymbolData.ExprData(return_type, False))
            return intrinsic
        elif intrinsic.name in ('uint8', 'uint32', 'uint64'):
            to_bits = int(intrinsic.name[4:])
            intrinsic.args = [self.visit_expr(arg) for arg in intrinsic.args]
            expected = [self.builtins.general().sint[64]]
            intrinsic.args = self.unify_arguments(intrinsic.args, expected, intrinsic)
            return_type = self.builtins.general().sint[to_bits]

            self.symbols.expr(intrinsic, set_to=SymbolData.ExprData(return_type, False))
            return intrinsic
        else:
            msg = DefinitionError.no_such_intrinsic(intrinsic.pos, intrinsic.name)
            MessageHandler.handle_message(msg)
            self.symbols.expr(intrinsic, set_to=SymbolData.ExprData(ErroredTypeSymbol(intrinsic, intrinsic.pos), False))
            return intrinsic

    def visit_lambda(self, lambda_: LambdaIR):
        for param in lambda_.params:
            self.visit_param(param)

        func_namespace = NamespaceSymbol(f"function <lambda>", lambda_, lambda_.pos)
        self.current_namespace.define_namespace(func_namespace, visible=False)
        for param in lambda_.params:
            self.visit_param(param)
            self.define_value(self.symbols.param(param).symbol, in_namespace=func_namespace)
        with self.enter_namespace(func_namespace):
            lambda_.body = self.visit_expr(lambda_.body)
        ret = self.symbols.expr(lambda_.body).return_type

        params = [self.symbols.type(param.type).resolved_type for param in lambda_.params]
        func_type = FunctionTypeSymbol(params, ret, lambda_, lambda_.pos)

        func_value = VariableSymbol("<lambda>", lambda_, func_type, lambda_.pos)

        self.symbols.decl(lambda_, set_to=SymbolData.DeclData(lambda_, func_value, func_type))
        self.symbols.lambda_(lambda_, set_to=SymbolData.LambdaData(func_value, func_type, func_namespace))
        self.symbols.expr(lambda_, set_to=SymbolData.ExprData(func_type, False))
        return lambda_

    def visit_get_static_attr_expr(self, get_static: GetStaticAttrExprIR):
        get_static.namespace = self.visit_namespace(get_static.namespace)
        namespace = self.symbols.namespace(get_static.namespace).resolved_namespace
        if isinstance(namespace, ErroredNamespaceSymbol):
            resolved_value = ErroredVariableSymbol(get_static, get_static.pos)
        else:
            resolved_value = self.lookup_value(get_static.attr, get_static, in_namespace=namespace)

        self.symbols.expr(get_static, set_to=SymbolData.ExprData(resolved_value.type, False))
        self.symbols.get_static_attr_expr(get_static, set_to=SymbolData.GetStaticAttrExprData(resolved_value))
        return get_static

    def visit_tuple(self, tuple: TupleIR):
        items = []
        for item in tuple.items:
            self.visit_expr(item)
            items.append(self.typeof(item))
        return_type = TupleTypeSymbol(items, tuple, tuple.pos)
        self.symbols.expr(tuple, set_to=SymbolData.ExprData(return_type, False))
        return tuple

    def visit_int(self, num: IntIR):
        # TODO Number size checking and handle the INT_MAX vs INT_MIN problem with unary - in front of a literal
        self.symbols.expr(num, SymbolData.ExprData(self.builtins.general().sint[32], False))
        return num

    def visit_ann(self, ann: AnnotationIR):
        ann.type = self.visit_type(ann.type)
        return ann

    def visit_get_namespace(self, namespace: GetNamespaceIR):
        resolved_namespace = self.lookup_namespace(namespace.name, namespace)
        self.symbols.namespace(namespace, set_to=SymbolData.NamespaceData(resolved_namespace))
        return namespace

    def visit_malformed_namespace(self, malformed: MalformedNamespaceIR):
        msg = MalformedASTError(f"Could resolve expression to a namespace", malformed.pos)
        MessageHandler.handle_message(msg)
        self.symbols.namespace(malformed, set_to=SymbolData.NamespaceData(ErroredNamespaceSymbol(malformed, malformed.pos)))
        return malformed
