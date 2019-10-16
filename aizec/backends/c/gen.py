import subprocess

from ...common.aize_ast import *
from . import _cgen as cgen


TCC_PATH = Path(__file__).absolute().parent.parent.parent / "tcc" / "tcc.exe"


STD_IMPORTS = [
    STD / "aize_builtins.h", STD / "aize_builtins.c",
    STD / "aize_mem.h", STD / "aize_mem.c",
    STD / "aize_common.h",
]


class CompilationError(AizeError):
    def __init__(self, msg: str):
        self.msg = msg

    def display(self, file: IO):
        file.write(f"{self.msg}.")


class CGenerator:
    def __init__(self, header: IO, source: IO):
        self.header = header
        self.source = source

        self.links: List[Path] = []

        self.main: NameDecl

    @classmethod
    def gen(cls, tree: Program):
        main_file = next(file.path for file in tree.files if file.is_main).with_suffix("")
        with main_file.with_suffix(".h").open("w") as header:
            with main_file.with_suffix(".c").open("w") as source:
                generator = cls(header, source)
                tops = generator.visit_Program(tree)
                program = cgen.Program(tops, main_file)
                program.generate(main_file.name.replace(".", "_"), header, source)
        return main_file.with_suffix(".c"), main_file.with_suffix(".h"), generator

    @classmethod
    def compile(cls, tree: Program, args):
        source, header, gen = cls.gen(tree)
        check = subprocess.run([str(TCC_PATH),
                                f"-o{args.out.as_posix()}",
                                "-w", f"{source}",
                                *(str(path) for path in gen.links)],
                               check=False)  #, shell=True)
        if args.delete_c:
            source.unlink()
            header.unlink()
        if check.returncode != 0:
            raise CompilationError("Compilation of generated C code failed")

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
            if ret is not None:
                tops.append(ret)
        return tops

    def visit_CImport(self, obj: CImport):
        if obj.source not in self.links:
            self.links.append(obj.source)
        return cgen.Include(obj.header.as_posix())

    def visit_Import(self, obj: Import):
        return None

    def visit_Function(self, obj: Function):
        body = [self.visit(stmt) for stmt in obj.body]
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
        return cgen.Return(self.visit(obj.val))

    def visit_Call(self, obj: Call):
        return cgen.Call(self.visit(obj.left), [self.visit(arg) for arg in obj.args])

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
