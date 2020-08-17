import lark

lalr_parser = lark.Lark.open("aize.lark", parser="lalr", lexer="standard", start="source", maybe_placeholders=True)
# earley_parser = lark.Lark.open("aize.lark", parser="earley", lexer="standard", ambiguity="explicit", start="source", maybe_placeholders=True)


with open(r"C:\Users\magil\Projects\aize-lang-v3\test.az", "r") as in_file:
    text = in_file.read()

prettified = lalr_parser.parse(text).pretty("    ")

with open("parsed.txt", "w") as out:
    out.write(prettified)
print(prettified)
