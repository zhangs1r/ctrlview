#!/usr/bin/env python3
"""站点生成器：把 posts/*.md 渲染成静态站。

用法: build_site.py <repo_root> <out_dir>
设计原则：
- 零 JS 零 CDN（沙箱与国内都不可达 jsdelivr），一切内联
- 手机/电脑双适配，公式用 MathML 原生渲染
- 论文原文链接必留（回 arXiv 下载 PDF）
"""
import os, re, sys, json, base64, html as H, glob, datetime, subprocess, shutil

# ---------- 站点级 CSS（与精读页共用一套设计语言） ----------
BASE_CSS = """
:root{
  --bg:#fbfaf8; --card:#fff; --ink:#1b1b1f; --ink2:#4a4a55; --ink3:#8a8a96;
  --line:#e6e4df; --accent:#2d5f8a; --accent-bg:#eef4f9; --ctrl:#8a5a2d; --ctrl-bg:#fdf5ec;
  --code:#f4f2ee; --maxw:740px; --wide:1080px;
}
@media (prefers-color-scheme:dark){
  :root{--bg:#16161a;--card:#1e1e24;--ink:#ececf0;--ink2:#b8b8c2;--ink3:#7c7c88;
        --line:#2e2e36;--accent:#7fb3d5;--accent-bg:#1c2a35;--ctrl:#d9a56b;--ctrl-bg:#2c2318;
        --code:#26262e}
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:17px/1.78 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  -webkit-text-size-adjust:100%}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:var(--maxw);margin:0 auto;padding:0 20px 96px}
.wrap.wide{max-width:var(--wide)}
header.top{padding:52px 0 28px;border-bottom:1px solid var(--line);margin-bottom:34px}
.kicker{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);font-weight:700}
h1{font-size:clamp(26px,5.2vw,38px);line-height:1.24;margin:14px 0 12px;letter-spacing:-.02em}
h2{font-size:clamp(19px,3.4vw,23px);margin:52px 0 16px;padding-top:16px;border-top:1px solid var(--line)}
h3{font-size:17px;margin:30px 0 10px;color:var(--ink)}
p{margin:15px 0}
ul,ol{padding-left:24px;margin:15px 0}li{margin:8px 0}
hr{border:0;border-top:1px solid var(--line);margin:40px 0}
strong{font-weight:680}
mark{background:linear-gradient(180deg,transparent 56%,var(--accent-bg) 56%);color:inherit;padding:0 .05em}
u{text-decoration:underline;text-decoration-color:var(--accent);
  text-decoration-thickness:1.5px;text-underline-offset:3px}
.meta{color:var(--ink3);font-size:14px;line-height:1.9}
.tags{margin-top:14px;display:flex;flex-wrap:wrap;gap:7px}
.tag{font-size:12px;padding:4px 11px;border-radius:99px;background:var(--accent-bg);color:var(--accent);font-weight:600}
figure{margin:28px 0}
figure img{width:100%;height:auto;display:block;border:1px solid var(--line);border-radius:10px;background:#fff}
figcaption{margin-top:11px;font-size:13.5px;line-height:1.7;color:var(--ink3)}
figcaption b{color:var(--ink2)}
aside.ctrl{margin:24px 0;padding:15px 18px;background:var(--ctrl-bg);border-left:3px solid var(--ctrl);
  border-radius:0 8px 8px 0;font-size:15.5px;line-height:1.75}
aside.ctrl b{color:var(--ctrl);display:block;margin-bottom:4px;font-size:12.5px;letter-spacing:.08em}
table{width:100%;border-collapse:collapse;margin:20px 0;font-size:14.5px}
th,td{padding:9px 11px;border-bottom:1px solid var(--line);text-align:left}
th{font-weight:680;color:var(--ink2);font-size:13px;background:var(--card)}
td:first-child{font-weight:600}tr:last-child td{border-bottom:none}
tr.hl td{background:var(--accent-bg);color:var(--accent);font-weight:700}
pre{background:var(--code);padding:15px 18px;border-radius:9px;overflow-x:auto;font-size:14px;
    font-family:ui-monospace,SFMono-Regular,Menlo,monospace;line-height:1.65;margin:18px 0;border:1px solid var(--line)}
pre code{background:none;padding:0}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.9em;background:var(--code);padding:2px 6px;border-radius:4px}
pre.flow{background:var(--code);border-left:3px solid var(--accent);font-size:13.5px;line-height:2;
  white-space:pre;overflow-x:auto;padding:16px 18px}
.eq{position:relative;margin:24px 0;padding:18px 52px;background:var(--card);
  border:1px solid var(--line);border-radius:10px;overflow-x:auto}
.eq .eqn{position:absolute;right:14px;top:50%;transform:translateY(-50%);
  font-size:12.5px;color:var(--ink3);font-weight:600;background:var(--bg);padding:2px 7px;
  border-radius:5px;border:1px solid var(--line)}
.eq math{font-size:1.02em;display:block;overflow-x:auto;overflow-y:hidden}
blockquote{margin:22px 0;padding:14px 20px;background:var(--card);border-left:3px solid var(--accent);
  border-radius:0 8px 8px 0;color:var(--ink2)}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.warn{background:rgba(190,80,40,.09);border-left:3px solid #b85028;padding:13px 17px;
  border-radius:0 8px 8px 0;margin:20px 0}
.fine{margin:18px 0;padding:2px 0 2px 14px;border-left:3px solid var(--line);
  font-size:13px;line-height:1.75;color:var(--ink3)}
.fine strong{color:var(--ink2)}
footer{color:var(--ink3);font-size:13px;text-align:center;padding:34px 0 0}
nav.bar{border-bottom:1px solid var(--line);padding:14px 0;margin-bottom:0;
  position:sticky;top:0;background:var(--bg);z-index:10}
nav.bar .inner{max-width:var(--wide);margin:0 auto;padding:0 20px;display:flex;gap:16px;
  align-items:center;flex-wrap:wrap}
nav.bar a{font-size:14px;color:var(--ink2);font-weight:600}
nav.bar a.on{color:var(--accent)}
nav.bar .brand{font-weight:700;color:var(--ink);margin-right:6px}
/* 卡片列表 */
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;margin:26px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;
  display:block;color:inherit}
.card:hover{border-color:var(--accent);text-decoration:none}
.card .cname{font-size:12px;color:var(--accent);font-weight:700;letter-spacing:.06em}
.card .ctitle{font-size:17px;font-weight:680;line-height:1.42;margin:8px 0 10px}
.card .cmeta{font-size:13px;color:var(--ink3);line-height:1.7}
.card .cabs{font-size:13.5px;color:var(--ink2);line-height:1.72;margin:0 0 11px}
.cards.abs{grid-template-columns:repeat(auto-fill,minmax(360px,1fr))}
.colsec{margin:10px 0 38px}
.colnote{color:var(--ink2);font-size:14.5px;margin:6px 0 0}
.badge{display:inline-block;font-size:11.5px;padding:3px 9px;border-radius:99px;
  background:var(--accent-bg);color:var(--accent);font-weight:600;margin-left:6px}
.paperlink{display:inline-block;margin:22px 0 0;padding:11px 18px;background:var(--accent-bg);
  color:var(--accent);border-radius:9px;font-size:14.5px;font-weight:650}
.paperlink:hover{text-decoration:none;background:var(--accent);color:#fff}
@media(max-width:600px){
  body{font-size:16.5px} .wrap{padding:0 16px 64px} header.top{padding:34px 0 22px}
  table{font-size:13.5px} th,td{padding:7px 8px}
  pre{padding:12px 14px;font-size:13px} pre.flow{font-size:12px;line-height:1.9}
  aside.ctrl{font-size:15px} .cards,.cards.abs{grid-template-columns:1fr;gap:12px}
  .eq{padding:14px 40px}
}
"""


BUILD = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
CSSFILE = "assets/app.css"
BUILD_HUMAN = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

# 公式转换失败的记录：静默降级成 <code class="tex-err"> 会让线上悄悄出现一屏 LaTeX 源码，
# 所以哪怕不中止构建，也必须在结尾把数量和样本打出来。
TEX_FAILS = []


def tex(latex, display=False):
    try:
        import latex2mathml.converter as C
        mml = C.convert(latex, display="block" if display else "inline")
        d = "block" if display else "inline"
        return f'<math xmlns="http://www.w3.org/1998/Math/MathML" display="{d}">{mml.split(">",1)[1] if ">" in mml else mml}</math>'
    except Exception as e:
        TEX_FAILS.append((latex.strip()[:60], type(e).__name__))
        return f'<code class="tex-err">{H.escape(latex)}</code>'


def cell_md(s):
    s = H.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    if "$" in s:
        s = re.sub(r"\$([^$]+)\$", lambda m: tex(m.group(1), False), s)
    return s


def inline_md(s):
    s = H.escape(s)
    # 行内公式与行内代码先摘出来占位，免得其中的 * _ = 被强调语法误伤
    stash = []

    def _stash(kind):
        def f(m):
            stash.append((kind, m.group(1)))
            return "\x00%d\x00" % (len(stash) - 1)
        return f

    s = re.sub(r"\$([^$]+)\$", _stash("math"), s)
    s = re.sub(r"`([^`]+)`", _stash("code"), s)
    s = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"==(.+?)==", r"<mark>\1</mark>", s)
    s = re.sub(r"__(.+?)__", r"<u>\1</u>", s)
    s = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", s)

    def _restore(m):
        kind, text = stash[int(m.group(1))]
        return f"<code>{text}</code>" if kind == "code" else tex(text, False)

    return re.sub(r"\x00(\d+)\x00", _restore, s)


def _eqnum(s):
    m = re.search(r"\\tag\{([^}]*)\}", s)
    return f"({m.group(1)})" if m else ""


def md2html(md, figdir=""):
    out, i = [], 0
    lines = md.split("\n")
    if lines and lines[0].strip() == "---":
        for k in range(1, len(lines)):
            if lines[k].strip() == "---":
                lines = lines[k + 1:]
                break
    while i < len(lines):
        s = lines[i].strip()

        if s.startswith("```"):
            i += 1
            blk = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                blk.append(lines[i]); i += 1
            i += 1
            out.append('<pre class="flow"><code>' + H.escape("\n".join(blk)) + "</code></pre>")
            continue

        if s.startswith("$$"):
            if s.count("$$") >= 2 and len(s.strip()) > 4:
                body, i = s[2:].split("$$", 1)[0], i + 1
            else:
                blk, i = [], i + 1
                while i < len(lines) and "$$" not in lines[i]:
                    blk.append(lines[i].strip()); i += 1
                body = "\n".join(blk); i += 1
            num = _eqnum(body)
            latex = re.sub(r"\\tag\{[^}]*\}", "", body).strip()
            out.append(f'<div class="eq"><span class="eqn">{num}</span>{tex(latex, True)}</div>')
            continue

        m = re.match(r'^<figure\s+src="([^"]+)"\s+caption="([^"]*)">', s)
        if m:
            src, cap = m.group(1), H.unescape(m.group(2))
            body = "\n".join(lines[i+1:])
            fm = re.search(r"<figcaption>(.*?)</figcaption>", body, re.S)
            fc = fm.group(1) if fm else cap
            out.append(f'<figure><img src="{figdir}{src}?v={BUILD}" alt="论文插图" loading="lazy" decoding="async">'
                       f"<figcaption>{fc}</figcaption></figure>")
            while i < len(lines) and "</figure>" not in lines[i]:
                i += 1
            i += 1; continue

        if s.startswith("<aside"):
            blk = []
            while i < len(lines) and "</aside>" not in lines[i]:
                blk.append(lines[i].strip()); i += 1
            i += 1
            inner = " ".join(x for x in blk if x)
            inner = re.sub(r"</?b>", lambda m: "<strong>" if ">" not in m.group(0) else "</strong>", inner)
            out.append(f"<aside class='ctrl'>{inner}</aside>"); continue

        if s.startswith("### "):
            out.append(f"<h3>{H.escape(s[4:])}</h3>"); i += 1; continue
        if s.startswith("## "):
            out.append(f"<h2>{H.escape(s[3:])}</h2>"); i += 1; continue
        if s.startswith("# "):
            out.append(f"<h1>{H.escape(s[2:])}</h1>"); i += 1; continue
        if s in ("---", "***", "___"):
            out.append("<hr>"); i += 1; continue
        if s.startswith(">"):
            blk = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                blk.append(lines[i].strip().lstrip(">").strip()); i += 1
            out.append("<blockquote><p>" + inline_md(" ".join(x for x in blk if x)) + "</p></blockquote>")
            continue
        if s.startswith("⚠"):
            out.append(f'<div class="warn">{cell_md(s.replace("⚠","",1).strip())}</div>'); i += 1; continue
        if s.startswith("※"):
            out.append(f'<div class="fine">{cell_md(s[1:].strip())}</div>'); i += 1; continue

        if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i+1].strip()):
            hdr = [x.strip() for x in s.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([x.strip() for x in lines[i].strip().strip("|").split("|")]); i += 1
            th = "".join(f"<th>{cell_md(x)}</th>" for x in hdr)
            tb = ""
            for r in rows:
                cls = " class='hl'" if r and ("本文" in r[0] or "InfiniHand" in r[0]) else ""
                tb += f"<tr{cls}>" + "".join(f"<td>{cell_md(x)}</td>" for x in r) + "</tr>"
            out.append(f'<div class="scroll"><table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div>')
            continue

        if re.match(r"^[-*]\s+", s) or re.match(r"^\d+\.\s+", s):
            ordered = bool(re.match(r"^\d+\.\s+", s))
            items = []
            while i < len(lines):
                t = lines[i].strip()
                if re.match(r"^[-*]\s+", t):
                    items.append(re.sub(r"^[-*]\s+", "", t)); i += 1
                elif re.match(r"^\d+\.\s+", t):
                    items.append(re.sub(r"^\d+\.\s+", "", t)); i += 1
                elif t.startswith("  ") and items and t.strip():
                    items[-1] += " " + t.strip(); i += 1
                else:
                    break
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline_md(x)}</li>" for x in items) + f"</{tag}>")
            continue

        if not s:
            i += 1; continue
        out.append(f"<p>{inline_md(s)}</p>")
        i += 1
    return "\n".join(out)


def parse_fm(md):
    fm = {}
    if md.startswith("---"):
        for ln in md.split("---", 2)[1].strip().split("\n"):
            if ":" in ln:
                k, v = ln.split(":", 1)
                fm[k.strip()] = v.strip().strip('"')
    return fm


def nav(active="", self_page="index.html"):
    return ('<nav class="bar"><div class="inner">'
            '<a class="brand" href="index.html">CtrlView</a>'
            f'<a href="index.html" class="{"on" if active=="home" else ""}">首页</a>'
            f'<a href="columns.html" class="{"on" if active=="cols" else ""}">栏目</a>'
            f'<a href="topics.html" class="{"on" if active=="topic" else ""}">主题</a>'
            f'<a href="glossary.html" class="{"on" if active=="gloss" else ""}">术语表</a>'
            f'<a href="search.html" class="{"on" if active=="search" else ""}">搜索</a>'
            f'<a href="history.html" class="{"on" if active=="hist" else ""}">历史</a>'
            f'<a href="archive.html" class="{"on" if active=="arch" else ""}">全部文章</a>'
            # 产物里所有页面都在 docs/ 同一层，所以这里必须是相对同级的 index，
            # 早先写成 ../index.html 会往上跳一层，直接 404。
            f'<a href="{self_page}?force={BUILD}" title="绕过 CDN 缓存，重新拉取本页">↻ 强制刷新</a>'
            '</div></nav>')


def build(repo, out):
    os.makedirs(out, exist_ok=True)
    col = json.load(open(f"{repo}/pipeline/columns.json", encoding="utf-8"))
    site, columns = col["site"], col["columns"]
    posts = []
    for f in sorted(glob.glob(f"{repo}/posts/*.md"), reverse=True):
        md = open(f, encoding="utf-8").read()
        fm = parse_fm(md)
        aid = os.path.basename(f)[:-3]
        posts.append({"id": aid, "fm": fm, "md": md})

    # CSS 外链 + 内容指纹：内容变 → URL 变 → CDN 必然回源，绕开 max-age=600
    import hashlib
    h = hashlib.sha256(BASE_CSS.encode()).hexdigest()[:8]
    CSSFILE = f"assets/app.{h}.css"
    os.makedirs(f"{out}/assets", exist_ok=True)
    open(f"{out}/{CSSFILE}", "w", encoding="utf-8").write(BASE_CSS)
    globals()["CSSFILE"] = CSSFILE

    # 图片：posts 里写的是 figs/xxx.png（相对产物根目录），
    # 所以 figs/ 必须被复制进产物目录，否则新文章的图全部 404。
    nfig = 0
    if os.path.isdir(f"{repo}/figs"):
        os.makedirs(f"{out}/figs", exist_ok=True)
        for f in glob.glob(f"{repo}/figs/*"):
            if os.path.isfile(f):
                shutil.copy2(f, os.path.join(out, "figs", os.path.basename(f)))
                nfig += 1

    # ---- 精读页 ----
    cname0 = {c["id"]: c["name"] for c in columns}

    # ---------- 共用索引：术语表 / 主题 / 相关 / 搜索 ----------
    def plain_body(md):
        """剥掉 front-matter、图表块和公式块，只留可读文字"""
        b = md.split("---", 2)[2] if md.startswith("---") else md
        b = re.sub(r"```.*?```", " ", b, flags=re.S)
        b = re.sub(r"<figure.*?</figure>", " ", b, flags=re.S)
        b = re.sub(r"\$\$.*?\$\$", " ", b, flags=re.S)
        b = re.sub(r"\$[^$\n]*\$", " ", b)
        return b

    def strip_md(s):
        s = re.sub(r"<[^>]+>", "", s)
        s = re.sub(r"[*=`>#]", "", s)
        return re.sub(r"\s+", " ", s).strip()

    def tags_of(p):
        raw = p["fm"].get("tags", "").strip().strip("[]")
        out = []
        for t in raw.split(","):
            t = t.strip().strip('"').strip("'").strip()
            if t:
                out.append(t)
        return out

    ptitle = {p["id"]: p["fm"].get("title", p["id"]) for p in posts}
    pmap = {p["id"]: p for p in posts}

    # 术语表：把每篇「名词速查」里的条目汇总
    gloss = {}
    for p in posts:
        m = re.search(r"##\s*名词速查\s*\n(.*?)(?=\n##|\Z)", p["md"], re.S)
        if not m:
            continue
        for line in m.group(1).split("\n"):
            line = line.strip()
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 2:
                continue
            term = strip_md(cells[0])
            if not term or term == "词" or set(term) <= set("-: "):
                continue
            g = gloss.setdefault(term, {"def": strip_md(cells[1]), "from": []})
            if p["id"] not in g["from"]:
                g["from"].append(p["id"])
            elif cells[1]:
                g["def"] = strip_md(cells[1])
    gloss_sorted = sorted(gloss.items(), key=lambda kv: kv[0])

    # 主题：按 front-matter 的 tags 聚合
    topics = {}
    for p in posts:
        for t in tags_of(p):
            topics.setdefault(t, []).append(p["id"])
    topics = dict(sorted(topics.items(), key=lambda kv: (-len(kv[1]), kv[0])))

    # 相关：正文互相提及 + data/relations.json 里的人工记录
    marks = {}
    for p in posts:
        m = re.search(r"[A-Za-z][A-Za-z0-9\-]{3,}", p["fm"].get("title", ""))
        if m:
            marks[m.group(0)] = p["id"]
    rel_p = f"{repo}/data/relations.json"
    curated = json.load(open(rel_p, encoding="utf-8")) if os.path.exists(rel_p) else {}
    MUT = ' style="color:var(--ink3);font-size:13px"'

    def related_html(p):
        body = plain_body(p["md"])
        inside, outside, used = [], [], set()
        for pid in ptitle:
            if pid == p["id"]:
                continue
            hit = pid in body or any(k in body for k, v in marks.items() if v == pid)
            if hit:
                used.add(pid)
                inside.append(f'<li><a href="{H.escape(pid)}.html">{H.escape(ptitle[pid])}</a>'
                              f'<span{MUT}>　正文提及</span></li>')
        for r in curated.get(p["id"], []):
            pid, name = r.get("arxiv", ""), r.get("name", "")
            note = H.escape(r.get("note", ""))
            tail = f'　{note}' if note else ""
            if pid and pid in ptitle:
                if pid in used:
                    continue
                used.add(pid)
                inside.append(f'<li><a href="{H.escape(pid)}.html">{H.escape(name)}</a>'
                              f'<span{MUT}>{tail or "　站上有精读"}</span></li>')
            elif pid:
                outside.append(f'<li><a href="https://arxiv.org/abs/{H.escape(pid)}" '
                               f'target="_blank" rel="noopener">{H.escape(name)}</a>'
                               f'<span{MUT}>　arXiv:{H.escape(pid)}{tail}</span></li>')
            else:
                outside.append(f'<li>{H.escape(name)}<span{MUT}>{tail}</span></li>')
        if not inside and not outside:
            return ""
        h = '<h2>相关</h2>'
        if inside:
            h += ('<p style="color:var(--ink2);font-size:14px">站上已有的精读</p><ul>'
                  + "".join(inside) + "</ul>")
        if outside:
            h += ('<p style="color:var(--ink2);font-size:14px">最接近的几项工作</p><ul>'
                  + "".join(outside) + "</ul>")
        return h

    def topic_links(p):
        ts = tags_of(p)
        if not ts:
            return ""
        return "".join(f'<a class="tag" href="topics.html#t-{H.escape(t)}">{H.escape(t)}</a>'
                       for t in ts)

    # 搜索索引：标题 + 栏目 + 标签 + 摘要片段
    search_rows = []
    for p in posts:
        b = strip_md(plain_body(p["md"]))
        b = re.sub(r"^#+.*?$", "", b, flags=re.M)
        search_rows.append({
            "id": p["id"],
            "t": p["fm"].get("title", ""),
            "c": cname0.get(p["fm"].get("column", ""), p["fm"].get("column", "")),
            "g": tags_of(p),
            "d": p["fm"].get("date", ""),
            "s": b[:180],
        })

    for p in posts:
        fm = p["fm"]
        cn = cname0.get(fm.get("column", ""), fm.get("column", ""))
        # 标签统一从 tags_of 取，顺带把老写法里残留的引号清掉，并链到主题页
        tags = topic_links(p)
        aid = p["id"]
        body = md2html(p["md"], figdir="figs/")
        doc = f"""<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{H.escape(fm.get('title',''))} · CtrlView</title>
<meta name="description" content="{H.escape(fm.get('title',''))}">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate, max-age=0">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<link rel="alternate" type="application/atom+xml" title="CtrlView" href="feed.xml">
<link rel="stylesheet" href="{CSSFILE}?v={BUILD}"></head><body>
{nav(self_page=f"{aid}.html")}
<div class="wrap">
<header class="top">
<div class="kicker">{H.escape(cn)} · 论文精读</div>
<h1>{H.escape(fm.get('title',''))}</h1>
<div class="meta"><b>{H.escape(fm.get('authors',''))}</b><br>
arXiv:{aid} · {H.escape(fm.get('date',''))} · 精读约 {H.escape(fm.get('read_time',''))}</div>
<div class="tags">{tags}</div>
</header>
{body}
{related_html(p)}
<a class="paperlink" href="https://arxiv.org/abs/{aid}" target="_blank" rel="noopener">
  查看论文原文 · 下载 PDF（arXiv:{aid}） →</a>
<footer>CtrlView · 用控制工程的视角读 AI 与机器人论文<br>本页构建于 {BUILD_HUMAN}</footer>
</div></body></html>"""
        open(f"{out}/{aid}.html", "w", encoding="utf-8").write(doc)

    def excerpt(p, n=150):
        """卡片摘要：取正文里第一段可读文字（去掉标题、表格、列表、引用块、小字块）"""
        b = plain_body(p["md"])
        b = re.sub(r"(?m)^\s*(?:#{1,6}\s.*|\|.*|[-*+]\s+.*|>.*|※.*|⚠.*|<.*)$", "", b)
        b = strip_md(b)
        b = re.sub(r"\s+", " ", b).strip()
        return (b[:n].rstrip() + "…") if len(b) > n else b

    def home_card(p):
        fm = p["fm"]
        return (f'<a class="card" href="{p["id"]}.html">'
                f'<div class="ctitle">{H.escape(fm.get("title",""))}</div>'
                f'<div class="cabs">{H.escape(excerpt(p))}</div>'
                f'<div class="cmeta">arXiv:{p["id"]} · {H.escape(fm.get("date",""))} · '
                f'精读约 {H.escape(fm.get("read_time",""))}</div></a>')

    # ---- 首页：按栏目分组，每张卡片带摘要 ----
    home_secs = ""
    for c in columns:
        ps = sorted([p for p in posts if p["fm"].get("column") == c["id"]],
                    key=lambda p: (p["fm"].get("date", ""), p["id"]), reverse=True)
        if not ps:
            continue
        home_secs += (
            f'<section class="colsec">'
            f'<h2 id="c-{c["id"]}">{c["name"]}<span class="badge">{len(ps)} 篇</span></h2>'
            f'<p class="colnote">{H.escape(c.get("note",""))}　'
            f'<a href="columns.html#c-{c["id"]}">栏目页 →</a></p>'
            f'<div class="cards abs">{"".join(home_card(p) for p in ps)}</div></section>')
    open(f"{out}/index.html", "w", encoding="utf-8").write(f"""<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{site['name']} · {site['tagline']}</title>
<meta name="description" content="{site['description']}">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate, max-age=0">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<link rel="alternate" type="application/atom+xml" title="CtrlView" href="feed.xml">
<link rel="stylesheet" href="{CSSFILE}?v={BUILD}"></head><body>
{nav('home')}
<div class="wrap wide">
<header class="top">
<div class="kicker">面向控制工程背景的论文精读</div>
<h1>{site['name']}</h1>
<p style="font-size:18px;color:var(--ink2);margin-top:0">{site['tagline']}</p>
</header>
<div style="background:var(--card);border:1px solid var(--line);border-radius:10px;
  padding:14px 18px;margin:24px 0;font-size:14px;color:var(--ink2);line-height:1.8">
<b>最后更新：{BUILD_HUMAN}</b>（北京时间）· 每周一 18:00 自动跑批<br>
<span style="color:var(--ink3)">若看到旧内容，点上方「↻ 强制刷新」，或用 Ctrl/Cmd + Shift + R 硬刷新。</span><br>
<span style="color:var(--ink2)">也可以 <a href="feed.xml">订阅 Atom</a>，或者直接
<a href="search.html">搜索</a>、翻<a href="topics.html">主题</a>、
查<a href="glossary.html">跨文章术语表</a>、看<a href="history.html">历史推荐</a>、
<a href="columns.html">全部栏目</a>。</span>
</div>
{home_secs}
<footer>每周一 18:00 自动更新 · 论文原文版权归原作者所有<br>最后更新：{BUILD_HUMAN}</footer>
</div></body></html>""")

    # ---- 栏目页 ----
    sec = ""
    for c in columns:
        ps = [p for p in posts if p["fm"].get("column") == c["id"]]
        inner = ("<p style=\"color:var(--ink3);font-size:14px\">该栏目暂时还没有精读。</p>"
                 if not ps else '<div class="cards">' + "".join(
                     (f'<a class="card" href="{p["id"]}.html">'
                      f'<div class="ctitle">{H.escape(p["fm"].get("title",""))}</div>'
                      f'<div class="cmeta">arXiv:{p["id"]}</div></a>') for p in ps) + "</div>")
        sec += (f'<h2 id="c-{c["id"]}">{c["name"]}'
                f'<span class="badge">{len(ps)} 篇</span></h2>'
                f'<p style="color:var(--ink2);font-size:14.5px">{H.escape(c.get("note",""))}</p>{inner}')
    open(f"{out}/columns.html", "w", encoding="utf-8").write(f"""<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>栏目 · CtrlView</title>
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<link rel="stylesheet" href="{CSSFILE}?v={BUILD}"></head><body>
{nav('cols', 'columns.html')}<div class="wrap">
<header class="top"><div class="kicker">全部栏目</div><h1>按领域浏览</h1>
<p style="color:var(--ink2)">一篇论文可能同时属于多个领域。每栏独立成页，交叉内容以交叉标签呈现。</p>
</header>{sec}<footer>CtrlView · 最后更新 {BUILD_HUMAN}</footer></div></body></html>""")

    # ---- 归档页 ----
    open(f"{out}/archive.html", "w", encoding="utf-8").write(f"""<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>全部文章 · CtrlView</title>
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<link rel="stylesheet" href="{CSSFILE}?v={BUILD}"></head><body>
{nav('arch', 'archive.html')}<div class="wrap wide">
<header class="top"><div class="kicker">全部文章</div><h1>归档（{len(posts)} 篇）</h1></header>
<div class="cards abs">{"".join(home_card(p) for p in posts)}</div><footer>CtrlView · 最后更新 {BUILD_HUMAN}</footer></div></body></html>""")

    # ---- 主题页（按 tags 聚合） ----
    tsec = ""
    for t, ids in topics.items():
        cards = "".join(
            f'<a class="card" href="{H.escape(pid)}.html">'
            f'<div class="cname">{H.escape(cname0.get(pmap[pid]["fm"].get("column", ""), ""))}</div>'
            f'<div class="ctitle">{H.escape(ptitle[pid])}</div>'
            f'<div class="cmeta">arXiv:{H.escape(pid)} · '
            f'{H.escape(pmap[pid]["fm"].get("read_time", ""))}</div></a>' for pid in ids)
        tsec += (f'<h2 id="t-{H.escape(t)}">{H.escape(t)}'
                 f'<span class="badge">{len(ids)} 篇</span></h2><div class="cards">{cards}</div>')
    if not tsec:
        tsec = '<p style="color:var(--ink3)">还没有任何主题。</p>'
    open(f"{out}/topics.html", "w", encoding="utf-8").write(f"""<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>主题 · CtrlView</title>
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<link rel="stylesheet" href="{CSSFILE}?v={BUILD}"></head><body>
{nav('topic', 'topics.html')}<div class="wrap wide">
<header class="top"><div class="kicker">主题</div><h1>按主题浏览</h1>
<p style="color:var(--ink2)">一篇论文可能落在多个主题下。主题来自每篇正文的标签，按篇数排序。</p>
</header>
{tsec}
<footer>CtrlView · 最后更新 {BUILD_HUMAN}</footer></div></body></html>""")

    # ---- 术语表（汇总每篇的「名词速查」） ----
    grows = ""
    for term, g in gloss_sorted:
        srcs = "、".join(f'<a href="{H.escape(i)}.html">{H.escape(ptitle[i])}</a>'
                        for i in g["from"])
        grows += (f'<tr><td style="white-space:nowrap;font-weight:600">{cell_md(term)}</td>'
                  f'<td>{cell_md(g["def"])}</td>'
                  f'<td style="font-size:13px">{srcs}</td></tr>')
    if not grows:
        grows = '<tr><td colspan="3" style="color:var(--ink3)">还没有任何术语。</td></tr>'
    open(f"{out}/glossary.html", "w", encoding="utf-8").write(f"""<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>术语表 · CtrlView</title>
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<link rel="stylesheet" href="{CSSFILE}?v={BUILD}"></head><body>
{nav('gloss', 'glossary.html')}<div class="wrap">
<header class="top"><div class="kicker">术语表</div><h1>跨文章术语速查</h1>
<p style="color:var(--ink2)">来自每篇末尾的「名词速查」，这里做了合并。同一个词在不同文章里的解释可能不同，右侧标了出处。</p>
</header>
<div class="scroll"><table><thead><tr><th>词</th><th>一句话解释</th><th>出处</th></tr></thead>
<tbody>{grows}</tbody></table></div>
<footer>CtrlView · 共 {len(gloss_sorted)} 条 · 最后更新 {BUILD_HUMAN}</footer></div></body></html>""")

    # ---- 搜索页（索引直接内联，不依赖外链与网络） ----
    import json as _json
    sdata = _json.dumps(search_rows, ensure_ascii=False).replace("</", "<\\/")
    open(f"{out}/search.html", "w", encoding="utf-8").write(f"""<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>搜索 · CtrlView</title>
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<link rel="stylesheet" href="{CSSFILE}?v={BUILD}"></head><body>
{nav('search', 'search.html')}<div class="wrap">
<header class="top"><div class="kicker">搜索</div><h1>站内搜索</h1>
<p style="color:var(--ink2)">匹配标题、栏目、主题和摘要。索引随页面一起加载，不联网也能用。</p>
</header>
<p><input id="q" type="search" placeholder="输入关键词，例如 初始化、漂移门控、VLA"
   style="width:100%;padding:12px 14px;font-size:16px;border:1px solid var(--line);
   border-radius:9px;background:var(--card);color:var(--ink)"></p>
<p style="color:var(--ink3);font-size:14px" id="n"></p>
<div id="r"></div>
<footer>CtrlView · 索引 {len(search_rows)} 篇 · 最后更新 {BUILD_HUMAN}</footer></div>
<script>
var D = {sdata};
var q = document.getElementById('q'), r = document.getElementById('r'), n = document.getElementById('n');
function esc(s) {{ return s.replace(/[&<>]/g, function (c) {{ return {{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]; }}); }}
function render() {{
  var k = q.value.trim().toLowerCase();
  var hit = k ? D.filter(function (x) {{
    return (x.t + ' ' + x.c + ' ' + x.g.join(' ') + ' ' + x.s).toLowerCase().indexOf(k) >= 0;
  }}) : D;
  n.textContent = k ? ('找到 ' + hit.length + ' 篇') : ('共 ' + D.length + ' 篇，输入关键词开始筛选');
  r.innerHTML = hit.map(function (x) {{
    return '<a class="card" href="' + x.id + '.html" style="margin:12px 0">'
      + '<div class="cname">' + esc(x.c) + ' · ' + esc(x.d) + '</div>'
      + '<div class="ctitle">' + esc(x.t) + '</div>'
      + '<div class="cmeta">' + esc(x.s) + '…</div>'
      + '<div class="tags">' + x.g.map(function (g) {{
          return '<span class="tag">' + esc(g) + '</span>'; }}).join('') + '</div></a>';
  }}).join('');
}}
q.addEventListener('input', render);
render();
</script>
</body></html>""")

    # ---- Atom 订阅 ----
    base = site.get("base", "").rstrip("/") + "/"
    feeds = sorted(posts, key=lambda x: x["fm"].get("date", ""), reverse=True)[:30]
    entries = ""
    for p in feeds:
        pid = p["id"]
        d = p["fm"].get("date", "") or BUILD_HUMAN[:10]
        link = f"{base}{pid}.html"
        entries += (f'  <entry>\n    <title>{H.escape(p["fm"].get("title", ""))}</title>\n'
                    f'    <link href="{H.escape(link)}"/>\n'
                    f'    <id>{H.escape(link)}</id>\n'
                    f'    <updated>{d}T00:00:00+08:00</updated>\n'
                    f'    <category term="{H.escape(cname0.get(p["fm"].get("column",""), ""))}"/>\n'
                    f'    <summary>{H.escape(strip_md(plain_body(p["md"]))[:300])}</summary>\n'
                    f'  </entry>\n')
    latest = (feeds[0]["fm"].get("date", "") if feeds else BUILD_HUMAN[:10])
    open(f"{out}/feed.xml", "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom">\n'
        f'  <title>{H.escape(site.get("name", "CtrlView"))}</title>\n'
        f'  <subtitle>{H.escape(site.get("tagline", ""))}</subtitle>\n'
        f'  <link href="{H.escape(base + "feed.xml")}" rel="self"/>\n'
        f'  <link href="{H.escape(base)}"/>\n'
        f'  <id>{H.escape(base)}</id>\n'
        f'  <updated>{latest}T00:00:00+08:00</updated>\n'
        f'{entries}</feed>\n')

    # ---- 历史页（每周推荐记录） ----
    hist_p = f"{repo}/data/history.json"
    rounds = json.load(open(hist_p, encoding="utf-8")).get("rounds", []) if os.path.exists(hist_p) else []
    cname = {c["id"]: c["name"] for c in columns}
    have = {p["id"]: p["fm"].get("title", "") for p in posts}

    n_pick = n_pub = 0
    secs = ""
    for r in sorted(rounds, key=lambda x: x.get("date", ""), reverse=True):
        rows = ""
        for k in r.get("picks", []):
            n_pick += 1
            pid = k.get("id", "")
            col = cname.get(k.get("column"), k.get("column", ""))
            title = have.get(pid) or k.get("title", pid)
            if pid in have:
                n_pub += 1
                link = f'<a href="{H.escape(pid)}.html">{H.escape(title)}</a>'
                mark = '<span class="tag">已精读</span>'
            else:
                link = (f'<a href="https://arxiv.org/abs/{H.escape(pid)}" target="_blank" '
                        f'rel="noopener">{H.escape(title)}</a>')
                mark = '<span class="tag" style="background:#fdf5ec;color:#8a5a2d">待精读</span>'
            rows += (f'<tr><td>{H.escape(col)}</td><td>{link}</td>'
                     f'<td style="white-space:nowrap">{H.escape(pid)}</td><td>{mark}</td></tr>')
        note = f'<p style="color:var(--ink3);font-size:14px;margin:6px 0 10px">{H.escape(r["note"])}</p>' if r.get("note") else ""
        secs += (f'<h2 id="r-{H.escape(r.get("id",""))}">{H.escape(r.get("id",""))}'
                 f'<span class="badge">{r.get("date","")} · {len(r.get("picks", []))} 篇</span></h2>'
                 f'{note}<div class="scroll"><table><thead><tr><th>栏目</th><th>论文</th>'
                 f'<th>arXiv</th><th>状态</th></tr></thead><tbody>{rows}</tbody></table></div>')

    if not secs:
        secs = '<p style="color:var(--ink3)">还没有任何一周的记录。</p>'

    open(f"{out}/history.html", "w", encoding="utf-8").write(f"""<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>历史推荐 · CtrlView</title>
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<link rel="stylesheet" href="{CSSFILE}?v={BUILD}"></head><body>
{nav('hist', 'history.html')}<div class="wrap">
<header class="top"><div class="kicker">历史</div><h1>每周推荐记录</h1>
<p style="color:var(--ink2)">每一轮的推荐都留在这里。已经写出精读的直接点标题进文章，还没写的给的是 arXiv 原文。</p>
</header>
<div style="background:var(--card);border:1px solid var(--line);border-radius:10px;
  padding:14px 18px;margin:24px 0;font-size:14px;color:var(--ink2);line-height:1.8">
累计 <b>{len(rounds)}</b> 轮，推荐 <b>{n_pick}</b> 篇，其中已精读 <b>{n_pub}</b> 篇。<br>
<span style="color:var(--ink3)">出现在这份记录里的论文不会再被后续轮次重复推荐。</span>
</div>
{secs}
<footer>CtrlView · 最后更新 {BUILD_HUMAN}</footer></div></body></html>""")

    print(f"OK  {len(posts)} 篇精读 -> {out}")
    print(f"   figs: {nfig} 个文件 -> {out}/figs/")
    print(f"   历史: {len(rounds)} 轮 / {n_pick} 篇推荐 (已精读 {n_pub})")
    for p in posts:
        print(f"   {p['id']}  {p['fm'].get('title','')[:46]}")
    if TEX_FAILS:
        print(f"\n⚠ 有 {len(TEX_FAILS)} 处公式转换失败，已降级为 LaTeX 源码：")
        for src, err in TEX_FAILS[:5]:
            print(f"   [{err}] {src}")
        print("   → 检查 LaTeX 语法，或确认 latex2mathml 已安装")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
