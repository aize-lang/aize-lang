from __future__ import annotations

import contextlib

from ...common.aize_ast import *


STD = Path(__file__).absolute().parent.parent.parent / "std"
AIZEIO_H = STD / "aizeio.h"
AIZEIO_C = STD / "aizeio.c"
AIZEIO = Table.new(TableType.C_FILE, {
    'test': NameDecl('test', FuncTypeNode([], Name('void'))).defined(FuncType([], VoidType()), 'test')
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


class SemanticAnalysis:
    def __init__(self, program: Program):
        self.table: Table = Table.new(
            TableType.GLOBAL,
            {},
            {
                "int": IntType(),
                'void': VoidType()
            },
            {}
        )

        self.file_table: Table = None

        self.files: Dict[Path, File] = {}

        self.program: Program = program
        self.file: File = None
        self.main_file: File = None

        self.stack = []

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
        self.stack.append(obj)
        val = getattr(self, "visit_"+name)(obj, *args, **kwargs)
        self.stack.pop()
        return val

    def visit_Program(self, obj: Program):
        for file in obj.files:
            file.table = self.table.child(TableType.FILE)
            if file.is_main:
                self.main_file = file

        classes = []
        for file in obj.files:
            with self.enter(file.table):
                for top in file.tops:
                    if isinstance(top, Class):
                        cls_type = new(ClassType)
                        top.type = cls_type
                        self.table.add_type(top.name, cls_type)
                        classes.append((file, top))

        for file, cls in classes:
            cls_type = cls.type
            with self.enter(file.table):
                cls_type.base = self.visit(cls.base)

                for name, type in cls.attrs.items():
                    cls_type.attrs[name] = self.visit(type)

                for name, method in cls.methods.items():
                    cls_type.methods[name] = self.method_type(method, cls_type)

        for file in obj.files:
            self.file = file
            self.visit(file)

        self.main_file.tops.append(Function('main', FuncTypeNode([], Name('int')), [], Name('int'), [
            Return(Call(GetVar(self.program.main.unique).define(ref=self.program.main), []))
        ]).defined(FuncType([], IntType()), 'main'))

    def visit_File(self, obj: File):
        with self.enter(obj.table):
            for top in obj.tops:
                self.visit(top)

    def visit_Class(self, obj: Class):
        base = self.visit(obj.base)
        obj.type.base = base

    def visit_CImport(self, obj: CImport):
        # TODO some means of reading c files directly
        if obj.header == AIZEIO_H and obj.source == AIZEIO_C:
            self.file_table.add_namespace("aizeio", AIZEIO)
            self.program.c_files.append((AIZEIO_H, AIZEIO_C))
        else:
            raise SemanticError("Cannot import c files", obj)

    def mangled_path(self):
        main_path = self.main_file.path
        main_dir = main_path.parent
        file_path = self.file.path
        rel_path = file_path.relative_to(main_dir)
        folders: Tuple[str, ...] = rel_path.parts[:-1]
        file = rel_path.with_suffix("").name
        return ''.join(f"D{len(folder)}{folder}" for folder in folders) + f"F{len(file)}{file}"

    def visit_Function(self, obj: Function):
        self.file_table.add_name(obj.name, obj)
        mangled = f"AF" + self.mangled_path() + f"{len(obj.name)}{obj.name}"
        obj.unique = mangled

        if self.file.is_main and obj.name == "main":
            self.program.main = obj

        func_table = self.table.child(TableType.SCOPE)
        with self.enter(func_table):
            for param in obj.args:
                self.table.add_name(param.name, param)

            for stmt in obj.body:
                self.visit(stmt)
        obj.type = FuncType([self.visit(param.type) for param in obj.args], self.visit(obj.ret))

    def visit_Return(self, obj: Return):
        self.visit(obj.val)

    def visit_ExprStmt(self, obj: ExprStmt):
        self.visit(obj.expr)

    def visit_Call(self, obj: Call):
        func: FuncType = self.visit(obj.left)
        args = []
        for arg in obj.args:
            args.append(self.visit(arg))
        obj.ret = func.ret
        return func.ret

    def visit_GetVar(self, obj: GetVar):
        decl = self.table.get_name(obj.name)
        obj.ref = decl
        return decl.type

    def visit_GetNamespaceName(self, obj: GetNamespaceName):
        namespace: Table = self.visit(obj.namespace)
        name = namespace.get_name(obj.attr)
        obj.pointed = name
        obj.ret = name.type
        return name.type

    def visit_GetNamespace(self, obj: GetNamespace):
        table = self.table.get_namespace(obj.namespace)
        obj.table = table
        return table

    def visit_Num(self, obj: Num):
        obj.ret = IntType()
        return IntType()

    def visit_Name(self, obj: Name):
        return self.table.get_type(obj.name)

    def method_type(self, func: Method, cls: ClassType):
        return FuncType([cls] + [self.visit(arg.type) for arg in func.args], self.visit(func.ret))
