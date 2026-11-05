"""Build the lab site: every folder in experiments/ becomes an entry, automatically.

  python3 site/build.py            writes site/dist/ (open site/dist/index.html)

For each experiments/<name>/ it reads the README (or the first .md file) and pulls out:
  - the name and subtitle from the first heading ("Ask first: find out what someone needs" -> name, subtitle)
  - the question: a "**Question...:**" line, else the first paragraph
  - the finding: the first results-style section ("Results", "Verdict", "What this says", "Where it stands"):
    the text after the heading's colon, a bolded line, or the first bullet
  - the numbers: the first table in that section, shown behind a "Show the numbers" toggle
  - the run note: the heading's parentheses, e.g. "(Kaggle, 2x T4, 0.6 h, free)"
  - the date: the folder's last commit, else the newest date written in the README
  - status: results / planned / set up
So a new experiment shows up on the next push with nothing else to do.

To promote one or fix a guess, add experiments/<name>/demo.json, any of:
  {"demo": "demos/<name>/",        a page under site/demos/ (a hand-built demo)
   "tier": "flagship",             listed at the top with the other demos
   "title": "...", "subtitle": "...", "question": "...", "finding": "...",
   "pitch": "...",                 one or two sentences for the demo's tile at the top
   "hide": true}                   leave it off the site
"""
import html
import json
import pathlib
import re
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DIST = SITE / "dist"
REPO_URL = "https://github.com/KealJones/lm-experiments"
RESULT_HEAD = re.compile(r"result|verdict|what (this|it) says|where it stands|finding|takeaway|for the template", re.I)
DATE = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")


# ---------------------------------------------------------------- markdown, just enough

def inline(md, base):
    """Inline markdown to HTML: code, bold, italics, links (relative links point at GitHub)."""
    parts = re.split(r"(`[^`]+`)", md)
    out = []
    for p in parts:
        if p.startswith("`") and p.endswith("`") and len(p) > 1:
            out.append(f"<code>{html.escape(p[1:-1])}</code>")
            continue
        p = html.escape(p, quote=False)
        p = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{link(m.group(2), base)}">{m.group(1)}</a>', p)
        p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
        p = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<em>\1</em>", p)
        out.append(p)
    return "".join(out)


def link(href, base):
    href = html.unescape(href)
    if re.match(r"[a-z]+:", href) or href.startswith("#"):
        return html.escape(href)
    return html.escape(f"{REPO_URL}/blob/main/{(base / href).as_posix()}".replace("/./", "/"))


def plain(md):
    md = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", md)
    return re.sub(r"[*`]", "", md).strip()


def blocks(lines):
    """Split markdown lines into ('heading', level, text) / ('para', text) / ('bullets', [..]) / ('table', rows)."""
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
        elif s.startswith("```"):
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                i += 1
            i += 1
        elif m := re.match(r"(#{1,6})\s+(.*)", s):
            out.append(("heading", len(m.group(1)), m.group(2)))
            i += 1
        elif s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            out.append(("table", rows))
        elif re.match(r"[-*] ", s):
            items = []
            while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith(("#", "|", "```")):
                t = lines[i].strip()
                if re.match(r"[-*] ", t):
                    items.append(t[2:])
                elif items:
                    items[-1] += " " + t
                i += 1
            out.append(("bullets", items))
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not re.match(r"(#|\||[-*] |```)", lines[i].strip()):
                para.append(lines[i].strip())
                i += 1
            out.append(("para", " ".join(para)))
    return out


# ---------------------------------------------------------------- reading one experiment

def is_label(text):
    """A paragraph that only introduces what follows, like "**What it says:**"."""
    return len(plain(text)) < 60 and plain(text).endswith(":")


def pick_finding(section):
    """The most finding-like text in a results section."""
    paras = [b[1] for b in section if b[0] == "para" and not is_label(b[1])]
    bullets = [x for b in section if b[0] == "bullets" for x in b[1]]
    for pick in (
        next((p for p in paras if re.match(r"\*\*", p)), None),          # a paragraph that opens in bold
        next((x for x in bullets if re.match(r"\*\*", x)), None),        # a bullet that opens in bold
        next((x for x in bullets if "**" in x), None),
        next((p for p in paras if "**" in p), None),
        bullets[0] if bullets else None,
        paras[0] if paras else None,
    ):
        if pick:
            return re.sub(r"^\d+\.\s+", "", pick)
    return ""


def first_sentence(text, limit=320):
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = re.search(r"^(.{60,%d}?[.!?])(\s|$)" % limit, text)
    return cut.group(1) if cut else text[:limit].rsplit(" ", 1)[0] + "…"


def git_date(folder):
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%cs", "--", str(folder)], cwd=ROOT,
                           capture_output=True, text=True, timeout=20)
        return r.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def readme_for(folder):
    for name in ("README.md", "RESULTS.md", "PLAN.md"):
        if (folder / name).exists():
            return folder / name
    mds = sorted(folder.glob("*.md"))
    return mds[0] if mds else None


def read_experiment(folder, summaries):
    name = folder.name
    over = {}
    if (folder / "demo.json").exists():
        over = json.loads((folder / "demo.json").read_text())
    if over.get("hide"):
        return None
    base = folder.relative_to(ROOT)
    readme = readme_for(folder)
    text = readme.read_text() if readme else ""
    bl = blocks(text.splitlines())

    title, subtitle = name, summaries.get(name, "")
    if bl and bl[0][0] == "heading":
        h = re.sub(r"\s*\(.*\)$", "", bl[0][2]).strip()
        if ":" in h and not h.lower().startswith(("results", "plan")):
            title, subtitle = [x.strip() for x in h.split(":", 1)]
        else:
            title = h
    title = re.sub(r":\s*(results|plan)\b.*$", "", title, flags=re.I).strip()

    question = ""
    for b in bl:
        if b[0] == "para" and re.match(r"\*\*Question[^*]*\*\*", b[1]):
            question = re.sub(r"^\*\*Question[^*]*\*\*\s*", "", b[1])
            break
    if not question:
        question = next((b[1] for b in bl[1:] if b[0] == "para"), "")
    question = first_sentence(question, 360)
    question = question[:1].upper() + question[1:]
    if subtitle.strip().lower() == title.strip().lower():
        subtitle = ""

    finding, table, run_note, has_results = "", None, "", False
    for idx, b in enumerate(bl):
        if b[0] == "heading" and b[1] >= 2 and RESULT_HEAD.search(b[2]):
            has_results = True
            head = b[2]
            if m := re.search(r"\(([^()]*(?:\([^()]*\)[^()]*)*)\)", head):
                run_note = plain(m.group(1).split(";")[0])
            after = re.sub(r"\([^)]*\)", "", head)
            if ":" in after and after.split(":", 1)[1].strip():
                finding = after.split(":", 1)[1].strip()
            section = []
            for nb in bl[idx + 1:]:
                if nb[0] == "heading" and nb[1] <= b[1]:
                    break
                section.append(nb)
            if not finding:
                finding = pick_finding(section)
            table = next((nb[1] for nb in section if nb[0] == "table" and len(nb[1]) > 1), None)
            break
    if not has_results and readme and readme.name not in ("README.md", "PLAN.md"):  # a RESULTS.md / GRADES.md as the main file
        has_results = True
        finding = pick_finding(bl[1:])
        table = next((b[1] for b in bl if b[0] == "table" and len(b[1]) > 1), None)
    results_files = sorted(p for p in folder.rglob("*.md") if re.search(r"RESULTS|GRADES", p.name) and p != readme)
    results_elsewhere = None
    if not has_results and results_files:  # ran, but the README doesn't sum it up yet
        has_results = True
        rf = results_files[0]
        results_elsewhere = (rf.relative_to(folder).as_posix(),
                             f"{REPO_URL}/blob/main/{rf.relative_to(ROOT).as_posix()}")

    planned = bool(re.search(r"plan only|not built yet|\(plan\b|nothing has been run", text[:1500], re.I))
    status = "results" if has_results else "planned" if planned or not readme else "set up"
    dates = sorted(DATE.findall(text))
    date = git_date(folder) or ("-".join(dates[-1]) if dates else "")

    return {
        "id": name,
        "title": over.get("title", title),
        "subtitle": over.get("subtitle", subtitle),
        "question": over.get("question", question),
        "finding": over.get("finding", first_sentence(finding, 420)),
        "run_note": run_note,
        "table": table[:9] if table else None,
        "status": status,
        "date": date,
        "demo": over.get("demo"),
        "pitch": over.get("pitch"),
        "tier": over.get("tier", "flagship" if over.get("demo") else "card"),
        "readme": f"{REPO_URL}/blob/main/{base.as_posix()}/{readme.name}" if readme else f"{REPO_URL}/tree/main/{base.as_posix()}",
        "results_elsewhere": results_elsewhere,
        "base": base,
    }


def root_summaries():
    """The one-liners in the top README's experiment list, used when a README has no subtitle."""
    out = {}
    readme = ROOT / "README.md"
    if readme.exists():
        for m in re.finditer(r"^- \[`([^`]+)`\]\([^)]*\) — (.+)$", readme.read_text(), re.M):
            out[m.group(1)] = re.sub(r"^[^:]+:\s*", "", m.group(2)) if ":" in m.group(2) else m.group(2)
    return out


# ---------------------------------------------------------------- page

STATUS_TEXT = {"results": "Results", "planned": "Planned", "set up": "Set up, no write-up yet"}


def nice_date(d):
    if not d:
        return ""
    y, m, day = d.split("-")
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    return f"{int(day)} {months[int(m) - 1]} {y}"


def render_table(rows, base):
    head, *body = rows
    th = "".join(f"<th>{inline(c, base)}</th>" for c in head)
    tr = "".join("<tr>" + "".join(f"<td>{inline(c, base)}</td>" for c in r) + "</tr>" for r in body)
    return f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def render_entry(e):
    b = e["base"]
    title = html.escape(e["title"])
    demo = (f'<a class="demo-link" href="{html.escape(e["demo"])}">Open the demo</a>' if e["demo"] else "")
    numbers = (f'<details class="numbers"><summary>Show the numbers</summary>{render_table(e["table"], b)}</details>'
               if e["table"] else "")
    if e["finding"]:
        finding = f'<p class="finding">{inline(e["finding"], b)}</p>'
    elif e["results_elsewhere"]:
        name, url = e["results_elsewhere"]
        finding = f'<p class="finding none">Ran, but the write-up isn\'t in the README yet. Raw results: <a href="{html.escape(url)}">{html.escape(name)}</a></p>'
    elif e["status"] == "planned":
        finding = '<p class="finding none">Planned. Nothing has run yet.</p>'
    else:
        finding = '<p class="finding none">Set up. No results written up yet.</p>'
    run_note = f'<span class="run">{html.escape(e["run_note"])}</span>' if e["run_note"] else ""
    return f"""
<article class="entry" id="{e['id']}" data-status="{e['status']}">
  <div class="margin">
    <time datetime="{e['date']}">{nice_date(e['date'])}</time>
    <span class="status status-{e['status'].replace(' ', '-')}">{STATUS_TEXT[e['status']]}</span>
  </div>
  <div class="body">
    <h3><a href="{e['readme']}">{title}</a></h3>
    {f'<p class="subtitle">{inline(e["subtitle"], b)}</p>' if e['subtitle'] else ''}
    {f'<p class="question">{inline(e["question"], b)}</p>' if e['question'] else ''}
    {finding}
    <div class="meta">{run_note}{demo}<a href="{e['readme']}">Read the write-up</a></div>
    {numbers}
  </div>
</article>"""


def render_flagship(e):
    b = e["base"]
    return f"""
<a class="flagship" href="{html.escape(e['demo'])}">
  <span class="flagship-title">{html.escape(e['title'])}</span>
  <span class="flagship-q">{inline(plain(e.get('pitch') or e['question']), b)}</span>
  <span class="flagship-go">Try it</span>
</a>"""


def page(entries):
    flagships = [e for e in entries if e["tier"] == "flagship" and e["demo"]]
    counts = {s: sum(e["status"] == s for e in entries) for s in STATUS_TEXT}
    filters = "".join(
        f'<button type="button" data-filter="{s}" aria-pressed="false">{STATUS_TEXT[s].split(",")[0]} '
        f'<span>{counts[s]}</span></button>' for s in STATUS_TEXT if counts[s])
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Small model lab</title>
<meta name="description" content="Keal Jones's experiments with small language models: what was asked, what happened, and demos you can run.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@500;600;700&family=JetBrains+Mono:wght@400;600&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="lab.css">
</head>
<body>
<header class="masthead">
  <p class="owner"><a href="https://kealjones.com">Keal Jones</a></p>
  <h1>Small model lab</h1>
  <p class="lede">Experiments with language models small enough to run on a phone. Each one starts with a question,
  and most end with an answer I didn't expect. Every number here comes from a run in
  <a href="{REPO_URL}">lm-experiments</a>, and this page rebuilds itself from that repo whenever I push.</p>
</header>
<main>
  {'<section class="flagships" aria-labelledby="demos-h"><h2 id="demos-h">Demos you can run</h2><div class="flagship-row">' + ''.join(render_flagship(e) for e in flagships) + '</div></section>' if flagships else ''}
  <section class="log" aria-labelledby="log-h">
    <div class="log-head">
      <h2 id="log-h">Every experiment</h2>
      <div class="filters" role="group" aria-label="Show only">{filters}</div>
    </div>
    {''.join(render_entry(e) for e in entries)}
  </section>
</main>
<footer><p>Built by <code>site/build.py</code> from {len(entries)} folders in <code>experiments/</code>. Models are named as their makers name them.</p></footer>
<script>
for (const b of document.querySelectorAll('.filters button')) {{
  b.addEventListener('click', () => {{
    const on = b.getAttribute('aria-pressed') !== 'true';
    document.querySelectorAll('.filters button').forEach(x => x.setAttribute('aria-pressed', 'false'));
    b.setAttribute('aria-pressed', String(on));
    document.querySelectorAll('.entry').forEach(e => {{ e.hidden = on && e.dataset.status !== b.dataset.filter; }});
  }});
}}
</script>
</body>
</html>
"""


def main():
    summaries = root_summaries()
    entries = [e for f in sorted((ROOT / "experiments").iterdir()) if f.is_dir()
               if (e := read_experiment(f, summaries))]
    entries.sort(key=lambda e: e["date"], reverse=True)
    entries.sort(key=lambda e: e["tier"] != "flagship")

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    shutil.copy(SITE / "lab.css", DIST / "lab.css")
    if (SITE / "demos").exists():
        shutil.copytree(SITE / "demos", DIST / "demos", ignore=shutil.ignore_patterns("*.py", "*.mjs", "__pycache__"))
    (DIST / "index.html").write_text(page(entries))
    (DIST / "experiments.json").write_text(json.dumps(
        [{k: v for k, v in e.items() if k != "base"} for e in entries], indent=1))
    (DIST / ".nojekyll").write_text("")
    print(f"built {len(entries)} entries into {DIST.relative_to(ROOT)}/")
    for e in entries:
        print(f"  {e['date'] or '----------'}  {e['status']:8}  {e['id']:16} {e['finding'][:70]!r}")


if __name__ == "__main__":
    main()
