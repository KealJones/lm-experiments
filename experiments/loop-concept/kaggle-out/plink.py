"""Plink: a tiny made-up language no model has ever seen, so its syntax can't have been memorised.

  python plink.py prog.plk        run a program (stdout = what it shows; syntax errors go to stderr, exit 2)

Line-based. Blocks close with `end`. Indentation is ignored. Lines starting with `note` are comments.

  let NAME be EXPR                      declare a variable
  set NAME to EXPR                      change it
  show EXPR[, EXPR...]                  print values separated by spaces, then a newline
  count NAME from EXPR to EXPR [by EXPR]   counting loop, both ends inclusive, step may be negative
  for each NAME in EXPR                 loop over the items of a list
  for each index NAME in EXPR           loop over positions 0 .. size-1 of a list
  while EXPR                            loop while true
  if EXPR / orif EXPR / otherwise       branches
  stop                                  leave the innermost loop
  end                                   close a block

Expressions: integers, "text", true/false, + - * div mod, = <> < > <= >=, and or not, & (join text), parentheses,
list(a, b, ...), item(xs, i), size(xs), text(n). Anything else (Python's print, range, [ ], ==, %, ...) is a syntax error.
"""
import re
import sys

BUILTINS = {"list": "_list", "item": "_item", "size": "_size", "text": "_text"}
WORDS = {"and": "and", "or": "or", "not": "not", "div": "//", "mod": "%", "true": "True", "false": "False"}
TOKEN = re.compile(r'\s*(?:(\d+)|("[^"]*")|([A-Za-z_][A-Za-z_0-9]*)|(<>|<=|>=|[-+*()<>=,&]))')


class PlinkError(Exception):
    pass


def expr(src, names, n):
    out, pos, src = [], 0, src.strip()
    if not src:
        raise PlinkError(f"line {n}: missing expression")
    while pos < len(src):
        m = TOKEN.match(src, pos)
        if not m or m.end() == pos:
            raise PlinkError(f"line {n}: can't read {src[pos:].strip()[:20]!r}")
        pos = m.end()
        num, s, word, op = m.groups()
        if num or s:
            out.append(num or s)
        elif word:
            if word in WORDS:
                out.append(WORDS[word])
            elif word in BUILTINS:
                out.append(BUILTINS[word])
            elif word in names:
                out.append("v_" + word)
            else:
                raise PlinkError(f"line {n}: unknown name {word!r}")
        else:
            out.append({"=": "==", "<>": "!=", "&": "+"}.get(op, op))
    code = " ".join(out)
    try:
        compile(code, "<expr>", "eval")
    except SyntaxError:
        raise PlinkError(f"line {n}: bad expression {src!r}")
    return code


def transpile(text):
    names, py, stack = set(), [], []  # stack: kinds of open blocks

    def emit(s):
        py.append("    " * (len(stack) + 1) + s)

    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line == "note" or line.startswith("note "):
            continue
        if m := re.fullmatch(r"let ([A-Za-z_]\w*) be (.+)", line):
            v, e = m.groups()
            if v in names or v in BUILTINS or v in WORDS:
                raise PlinkError(f"line {n}: {v!r} already declared")
            code = expr(e, names, n)
            names.add(v)
            emit(f"v_{v} = {code}")
        elif m := re.fullmatch(r"set ([A-Za-z_]\w*) to (.+)", line):
            v, e = m.groups()
            if v not in names:
                raise PlinkError(f"line {n}: set before let: {v!r}")
            emit(f"v_{v} = {expr(e, names, n)}")
        elif m := re.fullmatch(r"show (.+)", line):
            parts = [expr(p, names, n) for p in split_commas(m.group(1), n)]
            emit(f"_show({', '.join(parts)})")
        elif m := re.fullmatch(r"count ([A-Za-z_]\w*) from (.+?) to (.+?)(?: by (.+))?", line):
            v, a, b, step = m.groups()
            names.add(v)
            a, b = expr(a, names, n), expr(b, names, n)
            step = expr(step, names, n) if step else "1"
            emit(f"for v_{v} in _count({a}, {b}, {step}):")
            stack.append("loop")
        elif m := re.fullmatch(r"for each index ([A-Za-z_]\w*) in (.+)", line):
            v, e = m.groups()
            code = expr(e, names, n)
            names.add(v)
            emit(f"for v_{v} in range(_size({code})):")
            stack.append("loop")
        elif m := re.fullmatch(r"for each ([A-Za-z_]\w*) in (.+)", line):
            v, e = m.groups()
            code = expr(e, names, n)
            names.add(v)
            emit(f"for v_{v} in _items({code}):")
            stack.append("loop")
        elif m := re.fullmatch(r"while (.+)", line):
            emit(f"while _truth({expr(m.group(1), names, n)}):")
            stack.append("loop")
        elif m := re.fullmatch(r"if (.+)", line):
            emit(f"if _truth({expr(m.group(1), names, n)}):")
            stack.append("if")
        elif m := re.fullmatch(r"orif (.+)", line):
            if not stack or stack[-1] != "if":
                raise PlinkError(f"line {n}: orif outside an if")
            stack.pop()
            emit(f"elif _truth({expr(m.group(1), names, n)}):")
            stack.append("if")
        elif line == "otherwise":
            if not stack or stack[-1] != "if":
                raise PlinkError(f"line {n}: otherwise outside an if")
            stack.pop()
            emit("else:")
            stack.append("else")
        elif line == "stop":
            if "loop" not in stack:
                raise PlinkError(f"line {n}: stop outside a loop")
            emit("break")
        elif line == "end":
            if not stack:
                raise PlinkError(f"line {n}: end with nothing open")
            emit("pass")
            stack.pop()
        else:
            raise PlinkError(f"line {n}: can't read {line[:40]!r}")
    if stack:
        raise PlinkError(f"missing end ({len(stack)} block(s) still open)")
    return "def _main():\n    pass\n" + "\n".join(py) + "\n_main()\n"


def split_commas(s, n):
    parts, depth, cur, quote = [], 0, "", False
    for ch in s:
        if ch == '"':
            quote = not quote
        if not quote and ch == "(":
            depth += 1
        if not quote and ch == ")":
            depth -= 1
        if ch == "," and depth == 0 and not quote:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    if any(not p.strip() for p in parts):
        raise PlinkError(f"line {n}: empty value in show")
    return parts


class PlinkRuntimeError(Exception):
    pass


def _check_int(*xs):
    for x in xs:
        if isinstance(x, bool) or not isinstance(x, int):
            raise PlinkRuntimeError(f"expected a number, got {x!r}")


def _count(a, b, step):
    _check_int(a, b, step)
    if step == 0:
        raise PlinkRuntimeError("count step of 0")
    return range(a, b + (1 if step > 0 else -1), step)


def _items(xs):
    if not isinstance(xs, list):
        raise PlinkRuntimeError("for each needs a list")
    return list(xs)


def _list(*a):
    return list(a)


def _item(xs, i):
    if not isinstance(xs, list):
        raise PlinkRuntimeError("item needs a list")
    _check_int(i)
    if not 0 <= i < len(xs):
        raise PlinkRuntimeError(f"item {i} out of range")
    return xs[i]


def _size(xs):
    if not isinstance(xs, (list, str)):
        raise PlinkRuntimeError("size needs a list or text")
    return len(xs)


def _text(x):
    return x if isinstance(x, str) else str(x).lower() if isinstance(x, bool) else str(x)


def _truth(x):
    if not isinstance(x, bool):
        raise PlinkRuntimeError(f"condition must be true/false, got {x!r}")
    return x


def _show(*xs):
    print(" ".join(_text(x) for x in xs))


def run(text):
    code = transpile(text)
    env = {k: v for k, v in globals().items() if k.startswith("_") and callable(v)}
    exec(compile(code, "<plink>", "exec"), env)


if __name__ == "__main__":
    try:
        run(open(sys.argv[1]).read())
    except PlinkError as e:
        print(f"syntax error: {e}", file=sys.stderr)
        sys.exit(2)
    except (PlinkRuntimeError, TypeError, ZeroDivisionError, RecursionError) as e:
        print(f"runtime error: {e}", file=sys.stderr)
        sys.exit(3)
