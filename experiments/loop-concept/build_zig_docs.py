"""Turns Zig 0.17's language reference (doc/langref.html.in + doc/langref/*.zig from codeberg.org/ziglang/zig, tag 0.17.0,
MIT licensed) into one plain-text file the model can grep: docs/zig/langref.txt.

  python build_zig_docs.py LANGREF_HTML_IN EXAMPLES_DIR
"""
import html, pathlib, re, sys

src = pathlib.Path(sys.argv[1]).read_text()
ex = pathlib.Path(sys.argv[2])
body = src[src.find("{#header_open"):]


EXAMPLES = []


def code(m):  # leave a placeholder; examples go in after HTML is stripped so their < > survive
    f = ex / m.group(1)
    if not f.exists():
        return ""
    EXAMPLES.append(f"\n--- example {m.group(1)} ---\n{f.read_text().rstrip()}\n--- end example ---\n")
    return f"@@EXAMPLE{len(EXAMPLES) - 1}@@"


body = re.sub(r"\{#header_open\|([^#|]*)[^#]*#\}", lambda m: f"\n\n## {m.group(1)}\n", body)
body = re.sub(r"\{#code\|([^#]*)#\}", code, body)
body = re.sub(r"\{#syntax\|([^#]*)#\}", r"\1", body)
body = re.sub(r"\{#link\|([^#|]*)[^#]*#\}", r"\1", body)
body = re.sub(r"\{#[^#]*#\}", "", body)
body = re.sub(r"<pre>(.*?)</pre>", lambda m: m.group(1), body, flags=re.S)
body = re.sub(r"<li>", "- ", body)
body = re.sub(r"<[^>]+>", "", body)
body = html.unescape(body)
body = re.sub(r"@@EXAMPLE(\d+)@@", lambda m: EXAMPLES[int(m.group(1))], body)
body = re.sub(r"[ \t]+\n", "\n", body)
body = re.sub(r"\n{3,}", "\n\n", body)
out = pathlib.Path(__file__).parent / "docs/zig/langref.txt"
out.write_text("Zig 0.17.0 language reference (plain text)\n" + body.strip() + "\n")
print(out, len(body.splitlines()), "lines")
