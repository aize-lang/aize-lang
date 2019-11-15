from __future__ import annotations

import contextlib

from aizec.common.aize_ast import *
from aizec.common.error import AizeError
from aizec.common import new

# noinspection PyTypeChecker
ObjectType = ClassType('Object', [], {}, {})
ObjectType.structs = 'AizeObject'
ObjectType.cls_namespace = Table.new(TableType.CLASS, {}, {}, {})
# TODO finish Obj_namespace

StringType = ClassType('String', [], {}, {})
StringType.structs = 'AizeString'
StringType.cls_namespace = Table.new(TableType.CLASS, {
    'new': NameDecl.direct('new', 'AizeString_new', FuncType([], StringType))
}, {}, {})

ListType = ClassType('List', [], {}, {})
ListType.methods = {
    'add': Method.fake('add', [ListType, ObjectType], VoidType()),
    'get': Method.fake('Get', [ListType], ObjectType)
}
ListType.structs = 'AizeList'
ListType.cls_namespace = Table.new(TableType.CLASS, {
    'new': NameDecl.direct('new', 'AizeList_new', FuncType([], ListType))
}, {}, {})
ListType.obj_namespace = Table.new(TableType.OBJECT, {
    'add': NameDecl.direct('add', 'AizeList_append', FuncType([ListType, ObjectType], VoidType())),
    'get': NameDecl.direct('get', 'AizeList_get', FuncType([ListType], ObjectType))
}, {}, {})


AIZEIO = Table.new(TableType.C_FILE, {
    'test': NameDecl('test', FuncTypeNode([], Name('void'))).defined(FuncType([], VoidType()), 'test'),
    'print_int': NameDecl.direct('print_int', 'print_int', FuncType([IntType(), IntType()], VoidType())),
    'print': NameDecl.direct('print', 'print', FuncType([ObjectType], VoidType())),
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
                'List': ListType
            },
            {
                'List': ListType.cls_namespace
            }
        )

        self.file_table: Table = None

        self.files: Dict[Path, File] = {}

        self.program: Program = program
        self.file: File = None
        self.main_file: File = None
        self.function: Function = None

        self.max_methcall: int = 0
        self.curr_methcall: int = 0
        self.classes: List[ClassType] = [ObjectType, ListType]

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
        for file in obj.files:
            self.files[file.path] = file
            file.table = self.table.child(TableType.FILE)
            if file.is_main:
                self.main_file = file

        types = []
        for file in obj.files:
            self.file = file
            with self.enter(file.table):
                for top in file.tops:
                    if isinstance(top, Class):
                        cls_type = new(ClassType)
                        cls_type.name = top.name
                        top.type = cls_type
                        self.table.add_type(top.name, cls_type)
                        self.classes.append(cls_type)

                        cls_namespace = Table.empty(TableType.CLASS)
                        cls_type.cls_namespace = cls_namespace
                        self.table.add_namespace(top.name, cls_namespace)

                        obj_namespace = Table.empty(TableType.OBJECT)
                        cls_type.obj_namespace = obj_namespace

                        mangled = f"A{self.mangled_path()}C{len(top.name)}{top.name}"
                        top.unique = mangled
                        cls_type.structs = top.unique

                        cls_type.ttable = mangled + "_ttable"
                        cls_type.indices = []

                        cls_type.traits = []
                        cls_type.children = []

                        types.append((file, top))
                    elif isinstance(top, Trait):
                        trait_type = new(TraitType)
                        trait_type.name = top.name
                        top.type = trait_type
                        self.table.add_type(top.name, trait_type)

                        trait_namespace = Table.empty(TableType.TRAIT)
                        trait_type.trait_namespace = trait_namespace
                        self.table.add_namespace(top.name, trait_namespace)

                        obj_namespace = Table.empty(TableType.OBJECT)
                        trait_type.obj_namespace = obj_namespace

                        mangled = f"A{self.mangled_path()}T{len(top.name)}{top.name}"
                        top.unique = mangled
                        trait_type.unique = mangled

                        trait_type.ttable = mangled + "_ttable"
                        trait_type.indices = []

                        trait_type.children = []

                        types.append((file, top))

        for file in obj.files:
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

        for file, typ in types:
            if isinstance(typ, Class):
                cls = typ
                cls_type = cls.type
                cls_type.attrs = {}
                cls_type.methods = {}
                self.file = file
                with self.enter(file.table):
                    for trait in cls.traits:
                        trait_type = self.visit(trait)
                        cls_type.traits.append(trait_type)
                        trait_type.children.append(cls_type)

                    self.scope_names.append(f"{len(cls.name)}C{cls.name}")
                    for name, attr in cls.attrs.items():
                        self.visit(attr)
                        cls_type.attrs[name] = attr
                        cls_type.obj_namespace.add_name(name, attr)

                    for i, (name, method) in enumerate(cls.methods.items()):
                        method.unique = self.mangled_var(name, "M")
                        method.table = self.table.child(TableType.SCOPE)

                        method.owner = cls_type.get_owner(method.name)
                        if method.owner is cls_type:
                            cls_type.indices.append(method.name)

                        params = []
                        with self.enter(method.table):
                            for param in method.args:
                                self.visit(param)
                                self.table.add_name(param.name, param)
                                params.append(param.type)

                        method.type = FuncType(params, self.visit(method.ret))
                        cls_type.obj_namespace.add_name(name, method)

                        cls_type.methods[name] = method
                        # cls_type.ttable.append(method.name)

                    with self.enter(cls_type.cls_namespace):
                        new_type = FuncType([attr.type for attr in cls_type.attrs.values()], cls_type)
                        new_decl = NameDecl.direct("new", self.mangled_var("new", "S"), new_type)

                        self.table.add_name("new", new_decl)
                    self.scope_names.pop()
            elif isinstance(typ, Trait):
                trait = typ
                trait_type = trait.type
                trait_type.methods = {}
                self.file = file
                with self.enter(file.table):
                    # for trait in cls.traits:
                    #     cls_type.traits.append(self.visit(trait))

                    self.scope_names.append(f"C{len(trait.name)}{trait.name}")

                    for i, (name, method) in enumerate(trait.methods.items()):
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

                        trait_type.methods[name] = method

                        method.owner = trait_type.get_owner(method.name)
                        if method.owner is trait_type:
                            trait_type.indices.append(method.name)

                    self.scope_names.pop()

        for file in obj.files:
            self.file = file
            self.visit(file)

        self.main_file.tops.append(Function('main', FuncTypeNode([], Name('int')), [], Name('int'), [
            Return(Call(GetVar(self.program.main.unique).define(ref=self.program.main), []))
        ]).defined(FuncType([], IntType()), 'main'))

        obj.classes = self.classes

    def visit_File(self, obj: File):
        with self.enter(obj.table):
            for top in obj.tops:
                self.visit(top)

    def visit_Class(self, obj: Class):
        self.scope_names.append(f"C{len(obj.name)}{obj.name}")
        for method in obj.methods.values():
            self.visit(method)
        self.scope_names.pop()

    def visit_Trait(self, obj: Trait):
        self.scope_names.append(f"T{len(obj.name)}{obj.name}")
        for method in obj.methods.values():
            self.visit(method)
        self.scope_names.pop()

    def visit_Attr(self, obj: Attr):
        obj.type = self.visit(obj.type_ref)
        obj.unique = self.mangled_var(obj.name, typ='A')
        return obj.type

    def visit_Method(self, obj: Method):
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
        # TODO some means of reading c files directly
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
            # TODO equate types
            if obj.type != ret:
                raise TypeCheckError(obj.type, ret, obj)
                # raise SemanticError(f"Expected type {obj.type}, got {ret}", obj)
        obj.unique = self.mangled_var(obj.name)
        self.table.add_name(obj.name, obj)

    def visit_ExprStmt(self, obj: ExprStmt):
        self.visit(obj.expr)

    def visit_Call(self, obj: Call):
        func: FuncType = self.visit(obj.left)
        if MethodCall.is_method(obj)[0]:
            # noinspection PyUnresolvedReferences
            args = [obj.left.left.ret]
            MethodCall.make_method_call(obj, self.curr_methcall)
            self.curr_methcall += 1
        else:
            args = []
        if len(obj.args + args) != len(func.args):
            raise SemanticError(f"Function requires {len(func.args)} arguments, passed {len(obj.args)}", obj)
        for arg, func_arg in zip(obj.args, func.args):
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
        try:
            attr = left.obj_namespace.get_name(obj.attr)
        except KeyError:
            raise SemanticError(f"Object of type '{left.name}' does not have attribute '{obj.attr}'", obj)
        obj.pointed = attr
        obj.ret = attr.type
        return attr.type

    def visit_SetAttr(self, obj: SetAttr):
        left: ClassType = self.visit(obj.left)
        self.visit(obj.val)
        attr = left.obj_namespace.get_name(obj.attr)
        obj.pointed = attr
        obj.ret = attr.type
        return attr.type

    def visit_GetNamespaceName(self, obj: GetNamespaceName):
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

    def visit_Str(self, obj: Str):
        obj.ret = StringType
        return StringType

    def visit_Name(self, obj: Name):
        try:
            return self.table.get_type(obj.name)
        except KeyError:
            raise SemanticError(f"No type called '{obj.name}'", obj)
