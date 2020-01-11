from __future__ import annotations

import contextlib

from aizec.common.aize_ast import *
from aizec.common.error import AizeError
from aizec.common import AIZE_STD, IO


AIZEIO = Table.new(TableType.C_FILE, {
    'print_int': NameDecl.direct('print_int', 'print_int', FuncType([IntType(), IntType()], VoidType())),
    'print_space': NameDecl.direct('print_space', 'print_space', FuncType([], VoidType())),
    'get_time': NameDecl.direct("get_time", "get_time", FuncType([], IntType()))
}, {}, {})


class SemanticError(AizeError):
    def __init__(self, msg: str, node: Node):
        self.msg = msg
        self.node = node

    def display(self, file: IO):
        text_pos = self.node.pos
        line_no = text_pos.line
        line = text_pos.text.splitlines()[line_no-1]
        pos = text_pos.pos
        file.write(f"In {text_pos.file}:\n")
        file.write(f"Analysis Error: {self.msg}:\n")
        file.write(f"{line_no:>6} | {line}\n")
        file.write(f"         {' ' * pos[0]}{'^'*(pos[1]-pos[0])}")


class TypeCheckError(AizeError):
    def __init__(self, expected: Type, got: Type, node: Node):
        self.expected = expected
        self.got = got
        self.node = node

    def display(self, file: IO):
        text_pos = self.node.pos
        line_no = text_pos.line
        line = text_pos.text.splitlines()[line_no-1]
        pos = text_pos.pos
        file.write(f"In {text_pos.file}:\n")
        file.write(f"Type Checking Error: Expected type {self.expected}, got {self.got}:\n")
        file.write(f"{line_no:>6} | {line}\n")
        file.write(f"         {' ' * pos[0]}{'^'*(pos[1]-pos[0])}")


class SemanticAnalysis:
    # noinspection PyTypeChecker
    def __init__(self, program: Program):
        self.table: Table = Table.new(
            TableType.GLOBAL,
            {},
            {
                "int": IntType(),
                'void': VoidType(),
                'long': LongType(),
            },
            {}
        )

        self.global_table: Table = self.table
        self.file_table: Table = None

        self.files: Dict[Path, File] = {}

        self.program: Program = program
        self.file: File = None
        self.main_file: File = None
        self.function: Function = None

        self.max_methcall: int = 0
        self.curr_methcall: int = 0
        self.classes: List[ClassType] = []

        self.scope_names: List[str] = []

    @contextlib.contextmanager
    def enter(self, table: Table):
        old_table = self.table
        self.table = table

        if table.type == TableType.FILE:
            old_file_table = self.file_table
            self.file_table = table

            yield self.table

            self.file_table = old_file_table
        else:
            yield self.table

        self.table = old_table

    def ensure_valid(self, typ: Type, node: Node):
        if not isinstance(typ, (GenericClassType, GenericVar)):
            return typ
        else:
            raise SemanticError(f"Must specify types for Generic Class", node)

    def visit(self, obj, *args, **kwargs):
        name = obj.__class__.__name__
        val = getattr(self, "visit_"+name)(obj, *args, **kwargs)
        if isinstance(obj, Stmt):
            self.max_methcall = max(self.max_methcall, self.curr_methcall)
            self.curr_methcall = 0
        elif isinstance(obj, Expr):
            obj.ret = val
        return val

    def visit_Program(self, obj: Program):
        obj.needed_std.append('builtins')

        self.init_files(obj)

        types = []
        for file in obj.files:
            types += self.init_interfaced(file)

        for file in obj.files:
            self.init_funcs(file)

        for file, typ in types:
            if isinstance(typ, Class):
                self.finish_class(typ, file)
            elif isinstance(typ, Trait):
                self.finish_trait(typ, file)

        for file in obj.files:
            self.file = file
            self.visit(file)

        self.create_main()

        obj.classes = self.classes

    # region Program Init
    def init_files(self, obj: Program):
        for file in obj.files:
            self.files[file.path] = file
            file.table = self.table.child(TableType.FILE)
            if file.is_main:
                self.main_file = file

    def init_interfaced(self, file: File):
        types = []
        self.file = file
        if file.path == AIZE_STD / "__builtins__.aize":
            file_table = self.global_table
        else:
            file_table = file.table
        with self.enter(file_table):
            for top in file.tops:
                if isinstance(top, Class):
                    self.init_class(top)
                elif isinstance(top, Trait):
                    self.init_trait(top)
                elif isinstance(top, GenericClass):
                    self.init_generic_class(top)
                else:
                    continue
                types.append((file, top))
        return types

    def init_class(self, cls: Class):
        cls_type = ClassType(cls.name, [], {}, {})

        self.table.add_type(cls.name, cls_type)
        self.classes.append(cls_type)
        cls.type = cls_type

        cls_namespace = Table.empty(TableType.CLASS)
        cls_type.cls_namespace = cls_namespace
        self.table.add_namespace(cls.name, cls_namespace)

        obj_namespace = Table.empty(TableType.OBJECT)
        cls_type.obj_namespace = obj_namespace

        mangled = f"A{self.mangled_path()}C{len(cls.name)}{cls.name}"
        cls.unique = mangled
        cls_type.unique = cls.unique

        cls_type.ttable = mangled + "_ttable"
        cls_type.indices = []

        cls_type.parents = []
        cls_type.children = []

    def init_generic_class(self, gen_cls: GenericClass):
        gen_cls_type = GenericClassType(gen_cls, self.table)

        self.table.add_type(gen_cls.name, gen_cls_type)
        gen_cls.type = gen_cls_type

        gen_cls_namespace = GenericTable(gen_cls.type_vars, TableType.CLASS)
        gen_cls_type.cls_namespace = gen_cls_namespace
        self.table.add_namespace(gen_cls.name, gen_cls_namespace)

    def init_trait(self, trait: Trait):
        trait_type = TraitType(trait.name, [], {})
        trait.type = trait_type
        self.table.add_type(trait.name, trait_type)

        trait_namespace = Table.empty(TableType.TRAIT)
        trait_type.trait_namespace = trait_namespace
        self.table.add_namespace(trait.name, trait_namespace)

        obj_namespace = Table.empty(TableType.OBJECT)
        trait_type.obj_namespace = obj_namespace

        mangled = f"A{self.mangled_path()}T{len(trait.name)}{trait.name}"
        trait.unique = mangled
        trait_type.unique = mangled

        trait_type.ttable = mangled + "_ttable"
        trait_type.indices = []

        trait_type.children = []

    def init_funcs(self, file: File):
        self.file = file
        with self.enter(file.table):
            for top in file.tops:
                if isinstance(top, Function):
                    self.function = top
                    self.file_table.add_name(top.name, top)
                    mangled = f"A{self.mangled_path()}F{len(top.name)}{top.name}"
                    top.unique = mangled

                    if self.file.is_main and top.name == "main":
                        self.program.main = top

                    func_table = self.table.child(TableType.SCOPE)
                    top.table = func_table
                    with self.enter(func_table):
                        params = []
                        for param in top.args:
                            arg_ret = self.visit(param)
                            self.table.add_name(param.name, param)
                            params.append(arg_ret)
                        ret = self.visit(top.ret)
                    top.type = FuncType(params, ret)

    def finish_class(self, cls: Class, file: File):
        cls_type = cls.type
        cls_type.attrs = {}
        cls_type.methods = {}
        self.file = file
        with self.enter(file.table):
            for trait in cls.traits:
                trait_type = self.visit(trait)
                cls_type.parents.append(trait_type)
                trait_type.children.append(cls_type)

            self.scope_names.append(f"{len(cls.name)}C{cls.name}")
            for name, attr in cls.attrs.items():
                try:
                    owner = cls_type.get_owner(attr.name)
                except KeyError:
                    pass
                else:
                    if owner is not cls_type:
                        raise SemanticError(f"Name '{attr.name}' is already defined for {cls.name} in {owner.name}",
                                            attr)
                self.visit(attr)
                cls_type.attrs[name] = attr
                cls_type.obj_namespace.add_name(name, attr)

            for i, (name, method) in enumerate(cls.methods.items()):
                cls_type.interface[name] = method

                method.unique = self.mangled_var(name, "M")
                method.table = self.table.child(TableType.SCOPE)

                method.owner = cls_type.get_owner(method.name)

                params = []
                with self.enter(method.table):
                    for param in method.args:
                        self.visit(param)
                        self.table.add_name(param.name, param)
                        params.append(param.type)

                method.type = FuncType(params, self.visit(method.ret))
                cls_type.obj_namespace.add_name(name, method)

            with self.enter(cls_type.cls_namespace):
                new_type = FuncType([attr.type for attr in cls_type.attrs.values()], cls_type)
                new_decl = NameDecl.direct("new", self.mangled_var("new", "S"), new_type)

                self.table.add_name("new", new_decl)
            self.scope_names.pop()

    def finish_trait(self, trait: Trait, file: File):
        trait_type = trait.type
        trait_type.methods = {}
        self.file = file
        with self.enter(file.table):
            # for trait in cls.traits:
            #     cls_type.traits.append(self.visit(trait))

            self.scope_names.append(f"C{len(trait.name)}{trait.name}")

            for i, (name, method) in enumerate(trait.methods.items()):
                trait_type.interface[name] = method

                method.unique = self.mangled_var(name, "M")
                method.table = self.table.child(TableType.SCOPE)

                params = []
                with self.enter(method.table):
                    for param in method.args:
                        self.visit(param)
                        self.table.add_name(param.name, param)
                        params.append(param.type)

                method.type = FuncType(params, self.visit(method.ret))
                trait_type.obj_namespace.add_name(name, method)

                method.owner = trait_type.get_owner(method.name)

            self.scope_names.pop()

    def create_main(self):
        self.main_file.tops.append(Function('main', FuncTypeNode([], GetType('int')), [], GetType('int'), [
            Return(Call(GetVar(self.program.main.unique).define(ref=self.program.main), []))
        ]).defined(FuncType([], IntType()), 'main'))

    # endregion

    def visit_File(self, obj: File):
        with self.enter(obj.table):
            for top in obj.tops:
                self.visit(top)

    def visit_Class(self, obj: Class):
        self.scope_names.append(f"C{len(obj.name)}{obj.name}")
        for method in obj.methods.values():
            self.visit(method)
        self.scope_names.pop()

    def visit_GenericClass(self, obj: GenericClass):
        pass

    def visit_Trait(self, obj: Trait):
        self.scope_names.append(f"T{len(obj.name)}{obj.name}")
        for method in obj.methods.values():
            self.visit(method)
        self.scope_names.pop()

    def visit_Attr(self, obj: Attr):
        obj.type = self.visit(obj.type_ref)
        obj.unique = self.mangled_var(obj.name, typ='A')
        return obj.type

    def visit_ConcreteMethod(self, obj: ConcreteMethod):
        with self.enter(obj.table):
            self.scope_names.append(f"M{len(obj.name)}{obj.name}")
            if obj.body is not None:
                for stmt in obj.body:
                    self.visit(stmt)
            self.scope_names.pop()
        obj.temp_count = self.max_methcall
        self.max_methcall = 0
        self.curr_methcall = 0

    def visit_NativeImport(self, obj: NativeImport):
        if obj.name == 'aizeio':
            self.file_table.add_namespace("aizeio", AIZEIO)
            self.program.needed_std.append(obj.name)
        else:
            raise SemanticError(f"No Standard Library called {obj.name}", obj)

    def visit_Import(self, obj: Import):
        self.file_table.add_namespace(obj.as_name, self.files[obj.file.abs_path].table)

    def mangled_path(self):
        main_path = self.main_file.path
        main_dir = main_path.parent
        file_path = self.file.path
        backs = 0
        dir_on = main_dir
        while True:
            try:
                rel_path = file_path.relative_to(dir_on)
            except ValueError:
                dir_on = dir_on.parent
                backs += 1
            else:
                break
        folders: Tuple[str, ...] = rel_path.parts[:-1]
        file = rel_path.with_suffix("").name
        return 'B'*backs + ''.join(f"D{len(folder)}{folder}" for folder in folders) + f"F{len(file)}{file}"

    def mangled_var(self, name: str, typ: str = 'V'):
        return f"A{self.mangled_path()}{''.join(self.scope_names)}{typ}{len(name)}{name}"

    def visit_Function(self, obj: Function):
        self.function = obj
        with self.enter(obj.table):
            self.scope_names.append(f"F{len(obj.name)}{obj.name}")
            for stmt in obj.body:
                self.visit(stmt)
            self.scope_names.pop()
        obj.temp_count = self.max_methcall
        self.max_methcall = 0
        self.curr_methcall = 0

    def visit_Param(self, obj: Param):
        obj.type = self.visit(obj.type_ref)
        obj.unique = self.mangled_var(obj.name)
        return obj.type

    def visit_If(self, obj: If):
        self.visit(obj.cond)
        self.visit(obj.then_stmt)
        self.visit(obj.else_stmt)

    def visit_While(self, obj: While):
        self.visit(obj.cond)
        self.visit(obj.body)

    def visit_Block(self, obj: Block):
        obj.table = self.table.child(TableType.SCOPE)
        count = self.table.block_count
        obj.block_count = count
        with self.enter(obj.table):
            # max 100 nested scopes per scope
            self.scope_names.append(f"B{count:<02}")
            for stmt in obj.stmts:
                self.visit(stmt)
            self.scope_names.pop()
        self.table.block_count += 1

    def visit_Return(self, obj: Return):
        self.visit(obj.val)

    def visit_VarDecl(self, obj: VarDecl):
        ret = self.visit(obj.val)
        if obj.type_ref is None:
            obj.type = ret
        else:
            obj.type = self.visit(obj.type_ref)
            self.ensure_valid(obj.type, obj.type_ref)
            if not obj.type <= ret:
                raise TypeCheckError(obj.type, ret, obj)
                # raise SemanticError(f"Expected type {obj.type}, got {ret}", obj)
        obj.unique = self.mangled_var(obj.name)
        self.table.add_name(obj.name, obj)

    def visit_ExprStmt(self, obj: ExprStmt):
        self.visit(obj.expr)

    def visit_Call(self, obj: Call):
        func: FuncType = self.visit(obj.left)
        if obj.convert(self.curr_methcall):
            # noinspection PyUnresolvedReferences
            args = [obj.method_data.obj]
            func = obj.method_data.pointed.type
            self.curr_methcall += 1
        else:
            if not isinstance(func, FuncType):
                raise SemanticError(f"Cannot call {func}", obj)
            args = []

        if len(args+obj.args) != len(func.args):
            raise SemanticError(f"Function requires {len(func.args)} arguments, passed {len(obj.args)}", obj)
        for arg, func_arg in zip(args+obj.args, func.args):
            arg_ret = self.visit(arg)
            if not arg_ret <= func_arg:
                raise TypeCheckError(func_arg, arg_ret, obj)
        obj.ret = func.ret
        return func.ret

    def visit_LT(self, obj: LT):
        left = self.visit(obj.left)
        right = self.visit(obj.right)
        left_is_int = isinstance(left, (IntType, LongType))
        right_is_int = isinstance(right, (IntType, LongType))
        if left_is_int and right_is_int:
            obj.ret = BoolType()
        else:
            raise Exception()
        return obj.ret

    def visit_Add(self, obj: Add):
        self.visit(obj.left)
        self.visit(obj.right)
        return IntType()

    def visit_Sub(self, obj: Sub):
        self.visit(obj.left)
        self.visit(obj.right)
        return IntType()

    def visit_Div(self, obj: Div):
        self.visit(obj.left)
        self.visit(obj.right)
        return IntType()

    def visit_GetVar(self, obj: GetVar):
        try:
            decl = self.table.get_name(obj.name)
        except KeyError:
            raise SemanticError(f"Name '{obj.name}' not found", obj)
        obj.ref = decl
        obj.ret = decl.type
        return decl.type

    def visit_SetVar(self, obj: SetVar):
        decl = self.table.get_name(obj.name)
        obj.ref = decl
        val = self.visit(obj.val)
        if not val <= decl.type:
            raise TypeCheckError(decl.type, val, obj)
        return decl.type

    def visit_GetAttr(self, obj: GetAttr):
        left: ClassType = self.visit(obj.left)
        if not isinstance(left, ClassType):
            raise SemanticError(f"Left hand side must be a class", obj)
        try:
            attr = left.obj_namespace.get_name(obj.attr)
        except KeyError:
            raise SemanticError(f"Object of type '{left.name}' does not have attribute '{obj.attr}'", obj)
        obj.pointed = attr
        obj.pointed_cls = left
        obj.ret = attr.type
        return attr.type

    def visit_SetAttr(self, obj: SetAttr):
        left: ClassType = self.visit(obj.left)
        if not isinstance(left, ClassType):
            raise SemanticError(f"Left hand side must be a class", obj)
        try:
            attr = left.obj_namespace.get_name(obj.attr)
        except KeyError:
            raise SemanticError(f"Object of type '{left.name}' does not have attribute '{obj.attr}'", obj)
        self.visit(obj.val)
        attr = left.obj_namespace.get_name(obj.attr)
        obj.pointed = attr
        obj.pointed_cls = left
        obj.ret = attr.type
        return attr.type

    def visit_GetNamespaceExpr(self, obj: GetNamespaceExpr):
        namespace: Table = self.visit(obj.namespace)
        try:
            name = namespace.get_name(obj.attr)
        except KeyError:
            raise SemanticError(f"Namespace doesn't have the name '{obj.attr}'", obj)
        obj.pointed = name
        obj.ret = name.type
        return name.type

    def visit_GetNamespace(self, obj: GetNamespace):
        try:
            table = self.table.get_namespace(obj.namespace)
        except KeyError:
            raise SemanticError(f"No namespace found called '{obj.namespace}'", obj)
        obj.table = table
        return table

    def visit_Num(self, obj: Num):
        obj.ret = IntType()
        return IntType()

    def visit_GetType(self, obj: GetType):
        try:
            return self.table.get_type(obj.name)
        except KeyError:
            raise SemanticError(f"No type called '{obj.name}'", obj)
