"""Tiny OpenFormula subset for Pentaho style expressions.

Covers what the report bundles use for per-row styling, e.g.
``=IF(ISBLANK([ceo]); "none"; "solid")`` or ``=IF([payee]="";"false";"true")``:
field references, string/number literals, ``=`` / ``<>`` comparison and the
functions IF, ISBLANK, NOT, AND, OR, TRUE, FALSE. Anything else raises
FormulaError so the caller keeps the element's static style.
"""
import re

_TOKEN = re.compile(r'\s*(?:(\[[^\]]*\])|("(?:[^"]|"")*")|(\d+(?:\.\d+)?)|(<>|[=();,])|([A-Za-z_][A-Za-z0-9_.]*))')


class FormulaError(Exception):
    pass


def _tokenize(text):
    pos, tokens = 0, []
    text = text.strip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            raise FormulaError("cannot parse %r at %d" % (text, pos))
        field, string, number, op, name = m.groups()
        if field is not None:
            tokens.append(("field", field[1:-1]))
        elif string is not None:
            tokens.append(("str", string[1:-1].replace('""', '"')))
        elif number is not None:
            tokens.append(("num", float(number)))
        elif op is not None:
            tokens.append(("op", op))
        else:
            tokens.append(("name", name.upper()))
        pos = m.end()
    return tokens


def _equal(a, b):
    # Pentaho compares a NULL field against a string as the empty string
    if a is None and isinstance(b, str):
        a = ""
    if b is None and isinstance(a, str):
        b = ""
    return a == b


class _Parser(object):
    def __init__(self, tokens, row):
        self.tokens, self.pos, self.row = tokens, 0, row

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else (None, None)

    def take(self, kind=None, value=None):
        tok = self.peek()
        if tok[0] is None or (kind and tok[0] != kind) or (value is not None and tok[1] != value):
            raise FormulaError("unexpected %r" % (tok,))
        self.pos += 1
        return tok

    def expression(self):
        left = self.term()
        kind, value = self.peek()
        if kind == "op" and value in ("=", "<>"):
            self.take()
            right = self.term()
            return _equal(left, right) if value == "=" else not _equal(left, right)
        return left

    def term(self):
        kind, value = self.take()
        if kind == "field":
            return self.row.get(value)
        if kind in ("str", "num"):
            return value
        if kind == "name":
            self.take("op", "(")
            args = []
            if self.peek() != ("op", ")"):
                args.append(self.expression())
                while self.peek() in (("op", ";"), ("op", ",")):
                    self.take()
                    args.append(self.expression())
            self.take("op", ")")
            return self.call(value, args)
        if (kind, value) == ("op", "("):
            inner = self.expression()
            self.take("op", ")")
            return inner
        raise FormulaError("unexpected %r" % ((kind, value),))

    @staticmethod
    def call(name, args):
        if name == "IF" and len(args) in (2, 3):
            return args[1] if args[0] else (args[2] if len(args) == 3 else False)
        if name == "ISBLANK" and len(args) == 1:
            return args[0] is None
        if name == "NOT" and len(args) == 1:
            return not args[0]
        if name == "AND" and args:
            return all(args)
        if name == "OR" and args:
            return any(args)
        if name == "TRUE" and not args:
            return True
        if name == "FALSE" and not args:
            return False
        raise FormulaError("unsupported function %s/%d" % (name, len(args)))


def evaluate(formula, row):
    """Evaluate a style-expression formula against a data row."""
    text = (formula or "").strip()
    if text.startswith("="):
        text = text[1:]
    parser = _Parser(_tokenize(text), row or {})
    value = parser.expression()
    if parser.pos != len(parser.tokens):
        raise FormulaError("trailing tokens in %r" % formula)
    return value
