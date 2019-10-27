import io
import subprocess
import sys

from ...common.aize_ast import *
from . import _cgen as cgen


TCC_PATH = Path(__file__).absolute().parent.parent.parent / "tcc" / "tcc.exe"


STD_IMPORTS = [
    STD / "aize_builtins.h", STD / "aize_builtins.c",
    STD / "aize_common.h",
]


AIZE_BASE = cgen.PointerType(cgen.NameType('AizeBase'))


class CompilationError(AizeError):
    def __init__(self, msg: str):
        self.msg = msg

    def display(self, file: IO):
        file.write(f"{self.msg}.")


class CGenerator:
    def __init__(self, header: IO, source: IO, debug: bool):
        self.header = header
        self.source = source

        self.debug = debug

        self.links: List[Path] = []
        self.main: NameDecl

        self.in_main_main = False

    @classmethod
    def gen(cls, tree: Program, **kwargs):
        main_file = next(file.path for file in tree.files if file.is_main).with_suffix("")
        with main_file.with_suffix(".h").open("w") as header:
            with main_file.with_suffix(".c").open("w") as source:
                generator = cls(header, source, **kwargs)
                tops = generator.visit_Program(tree)
                program = cgen.Program(tops, main_file)
                program.generate(main_file.name.replace(".", "_"), header, source)
        return main_file.with_suffix(".c"), main_file.with_suffix(".h"), generator

    @classmethod
    def compile(cls, tree: Program, args):
        source, header, gen = cls.gen(tree, debug=args.debug)
        call_args = [str(TCC_PATH)]
        call_args += ["-w"]

        call_args += [f"-o{args.out.as_posix()}"]
        call_args += [f"{source}"]
        call_args += [str(path) for path in gen.links]

        check = subprocess.run(call_args, check=False)
        if args.delete_c:
            source.unlink()
            header.unlink()
        if check.returncode != 0:
            raise CompilationError(f"Compilation of generated C code failed (Exit Code {hex(check.returncode)})")

        if args.run:
            ret = subprocess.run(args.out.as_posix(), check=False)
            if ret.returncode == 0xc0000005:
                raise CompilationError(f"Running of generated executable failed (Segmentation Fault)")
            elif ret.returncode != 0:
                raise CompilationError(f"Running of generated executable failed ({hex(ret.returncode)})")

    def visit(self, obj):
        return getattr(self, "visit_"+obj.__class__.__name__)(obj)

    def visit_Program(self, obj: Program):
        tops = []

        for imp in STD_IMPORTS:
            if imp.suffix == ".c":
                self.links.append(imp)
            elif imp.suffix == ".h":
                tops.append(cgen.Include(imp.as_posix()))
        # TODO link the .c
        for file in obj.files:
            tops.extend(self.visit(file))
        return tops

    def visit_File(self, obj: File):
        tops = []
        for top in obj.tops:
            ret = self.visit(top)
            if isinstance(ret, (list, tuple)):
                tops.extend(ret)
            elif ret is not None:
                tops.append(ret)
        return tops

    def visit_CImport(self, obj: CImport):
        if obj.source not in self.links:
            self.links.append(obj.source)
        return cgen.Include(obj.header.as_posix())

    def visit_Import(self, obj: Import):
        return None

    def visit_Class(self, obj: Class):
        # TODO when types are a thing, a mechanism to add that to main?
        cls_ptr = self.visit(obj.type)
        if obj.base is None:
            attrs = {'base': cgen.StructType('AizeBase')}
        else:
            attrs = {'base': self.visit(obj.type.base)}
        attrs.update({attr.unique: self.visit(attr.type) for attr in obj.attrs.values()})
        cls_struct = cgen.Struct(obj.unique, attrs)

        new_unique = obj.type.cls_namespace.get_name("new").unique
        new_attrs = {attr.unique: self.visit(attr.type) for attr in obj.attrs.values()}
        new_func = cgen.Function(new_unique, new_attrs, cls_ptr, [
            cgen.Declare(cls_ptr, "mem", cgen.Call(cgen.GetVar("aize_mem_malloc"), [cgen.SizeOf(cls_struct.struct_type)])),
            cgen.Return(cgen.GetVar("mem")),
        ])

        return [cls_struct, new_func]

    def visit_ClassType(self, obj: ClassType):
        return cgen.PointerType(cgen.StructType(obj.structs))

    def visit_Function(self, obj: Function):
        body = []

        for i in range(obj.temp_count):
            body.append(cgen.Declare(cgen.void_ptr(), f"AT{i}", None))

        if obj.unique != 'main':
            body.append(cgen.ExprStmt(cgen.Call(cgen.GetVar("aize_mem_enter"), [])))
            self.in_main_main = False
        else:
            body.append(cgen.ExprStmt(cgen.Call(cgen.GetVar("aize_mem_init"), [])))
            self.in_main_main = True

        for stmt in obj.body:
            ret = self.visit(stmt)
            if self.debug:
                body.append(cgen.Comment(f"{stmt}"))
                body.append(cgen.printf(str(stmt)))
            if isinstance(ret, (list, tuple)):
                body.extend(ret)
            elif ret is not None:
                body.append(ret)

        if len(obj.body) == 0 or not isinstance(obj.body[-1], Return):
            body.append(cgen.ExprStmt(cgen.Call(cgen.GetVar("aize_mem_exit"), [])))

        return cgen.Function(obj.unique,
                             {param.unique: self.visit(param.type) for param in obj.args},
                             self.visit(obj.type.ret),
                             body)

    def visit_ExprStmt(self, obj: ExprStmt):
        return cgen.ExprStmt(self.visit(obj.expr))

    def visit_If(self, obj: If):
        return cgen.If(self.visit(obj.cond), self.visit(obj.then_stmt), self.visit(obj.else_stmt))

    def visit_While(self, obj: While):
        return cgen.While(self.visit(obj.cond), self.visit(obj.body))

    def visit_Block(self, obj: Block):
        return cgen.Block([self.visit(stmt) for stmt in obj.stmts])

    def visit_VarDecl(self, obj: VarDecl):
        return cgen.Declare(self.visit(obj.type), obj.unique, self.visit(obj.val))

    def visit_Return(self, obj: Return):
        if self.in_main_main:
            return cgen.Return(self.visit(obj.val))
        exit_call = cgen.ExprStmt(cgen.Call(cgen.GetVar("aize_mem_exit"), []))
        return [exit_call, cgen.Return(self.visit(obj.val))]

    def visit_Call(self, obj: Call):
        if obj.method_call is not None:
            return self.visit(obj.method_call)
        return cgen.Call(self.visit(obj.left), [self.visit(arg) for arg in obj.args])

    def visit_MethodCall(self, obj: MethodCall):
        # TODO
        left = self.visit(obj.obj)
        left = cgen.SetVar(f"AT{obj.depth}", left)
        # noinspection PyTypeChecker
        left = cgen.Cast(left, AIZE_BASE)
        left = cgen.GetArrow(left, 'vtable')
        left = cgen.GetItem(left, 0)
        left = cgen.Cast(left, self.visit(obj.pointed.type))
        left = cgen.Call(left, [cgen.GetVar(f"AT{obj.depth}")] + [self.visit(arg) for arg in obj.args])
        return left

    def visit_LT(self, obj: LT):
        return cgen.BinOp(self.visit(obj.left), '<', self.visit(obj.right))

    def visit_Add(self, obj: Add):
        return cgen.BinOp(self.visit(obj.left), '+', self.visit(obj.right))

    def visit_Sub(self, obj: Sub):
        return cgen.BinOp(self.visit(obj.left), '-', self.visit(obj.right))

    def visit_GetVar(self, obj: GetVar):
        return cgen.GetVar(obj.ref.unique)

    def visit_SetVar(self, obj: SetVar):
        return cgen.SetVar(obj.ref.unique, self.visit(obj.val))

    def visit_GetAttr(self, obj: GetAttr):
        return cgen.GetArrow(self.visit(obj.left), obj.pointed.unique)

    def visit_SetAttr(self, obj: SetAttr):
        return cgen.SetArrow(self.visit(obj.left), obj.pointed.unique, self.visit(obj.val))

    def visit_Num(self, obj: Num):
        return cgen.Constant(obj.num)

    # TODO for this and SemAnal, Make expr visitors and stmt visitors sep
    #  OR
    #  Make GetNamespaceAttr expr only, and make something else for getting types

    def visit_GetNamespaceName(self, obj: GetNamespaceName):
        return cgen.GetVar(obj.pointed.unique)

    def visit_IntType(self, obj: IntType):
        return cgen.IntType()

    def visit_LongType(self, obj: LongType):
        return cgen.LongType()

    def visit_VoidType(self, obj: VoidType):
        return cgen.VoidType()

    def visit_FuncType(self, obj: FuncType):
        return cgen.FunctionType([self.visit(arg) for arg in obj.args], self.visit(obj.ret))
