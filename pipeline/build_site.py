#!/usr/bin/env python3
"""站点生成器：把 posts/*.md 渲染成静态站。

用法: build_site.py <repo_root> <out_dir>
设计原则：
- 零 JS 零 CDN（沙箱与国内都不可达 jsdelivr），一切内联
- 手机/电脑双适配，公式用 MathML 原生渲染
- 论文原文链接必留（回 arXiv 下载 PDF）
"""
import os, re, sys, json, base64, html as H, glob, datetime, subprocess

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
.badge{display:inline-block;font-size:11.5px;padding:3px 9px;border-radius:99px;
  background:var(--accent-bg);color:var(--accent);font-weight:600;margin-left:6px}
.paperlink{display:inline-block;margin:22px 0 0;padding:11px 18px;background:var(--accent-bg);
  color:var(--accent);border-radius:9px;font-size:14.5px;font-weight:650}
.paperlink:hover{text-decoration:none;background:var(--accent);color:#fff}
@media(max-width:600px){
  body{font-size:16.5px} .wrap{padding:0 16px 64px} header.top{padding:34px 0 22px}
  table{font-size:13.5px} th,td{padding:7px 8px}
  pre{padding:12px 14px;font-size:13px} pre.flow{font-size:12px;line-height:1.9}
  aside.ctrl{font-size:15px} .cards{grid-template-columns:1fr;gap:12px}
  .eq{padding:14px 40px}
}
"""


BUILD = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
CSSFILE = "assets/app.css"
BUILD_HUMAN = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def tex(latex, display=False):
    try:
        import latex2mathml.converter as C
        mml = C.convert(latex, display="block" if display else "inline")
        d = "block" if display else "inline"
        return f'<math xmlns="http://www.w3.org/1998/Math/MathML" display="{d}">{mml.split(">",1)[1] if ">" in mml else mml}</math>'
    except Exception:
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
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', s)
    return s


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

        if re.search(r"\$[^$]+\$", s):
            out.append("<p>" + re.sub(r"\$([^$]+)\$",
                        lambda m: tex(m.group(1), False), inline_md(s)) + "</p>")
            i += 1; continue

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

        if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i+1].strip()):
            hdr = [x.strip() for x in s.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([x.strip() for x in lines[i].strip().strip("|").split("|")]); i += 1
            th = "".join(f"<th>{H.escape(x)}</th>" for x in hdr)
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


def nav(active=""):
    return ('<nav class="bar"><div class="inner">'
            '<a class="brand" href="../index.html">CtrlView</a>'
            f'<a href="../index.html" class="{"on" if active=="home" else ""}">首页</a>'
            f'<a href="../columns.html" class="{"on" if active=="cols" else ""}">栏目</a>'
            f'<a href="../archive.html" class="{"on" if active=="arch" else ""}">全部文章</a>'
            f'<a href="../index.html?force={BUILD}" title="绕过 CDN 缓存">↻ 强制刷新</a>'
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

    # ---- 精读页 ----
    cname0 = {c["id"]: c["name"] for c in columns}
    for p in posts:
        fm = p["fm"]
        cn = cname0.get(fm.get("column", ""), fm.get("column", ""))
        tags = "".join(f'<span class="tag">{H.escape(t.strip())}</span>'
                       for t in fm.get("tags", "[]").strip("[]").split(",") if t.strip())
        aid = p["id"]
        body = md2html(p["md"], figdir="../figs/")
        doc = f"""<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{H.escape(fm.get('title',''))} · CtrlView</title>
<meta name="description" content="{H.escape(fm.get('title',''))}">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate, max-age=0">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<link rel="stylesheet" href="{CSSFILE}?v={BUILD}"></head><body>
{nav()}
<div class="wrap">
<header class="top">
<div class="kicker">{H.escape(cn)} · 论文精读</div>
<h1>{H.escape(fm.get('title',''))}</h1>
<div class="meta"><b>{H.escape(fm.get('authors',''))}</b><br>
arXiv:{aid} · {H.escape(fm.get('date',''))} · 精读约 {H.escape(fm.get('read_time',''))}</div>
<div class="tags">{tags}</div>
</header>
{body}
<a class="paperlink" href="https://arxiv.org/abs/{aid}" target="_blank" rel="noopener">
  查看论文原文 · 下载 PDF（arXiv:{aid}） →</a>
<footer>CtrlView · 用控制工程的视角读 AI 与机器人论文<br>本页构建于 {BUILD_HUMAN}</footer>
</div></body></html>"""
        open(f"{out}/{aid}.html", "w", encoding="utf-8").write(doc)

    def card(p):
        fm = p["fm"]
        return (f'<a class="card" href="{p["id"]}.html">'
                f'<div class="cname">{H.escape(fm.get("column",""))}</div>'
                f'<div class="ctitle">{H.escape(fm.get("title",""))}</div>'
                f'<div class="cmeta">{H.escape(fm.get("authors",""))}<br>'
                f'arXiv:{p["id"]} · {H.escape(fm.get("read_time",""))}</div></a>')

    cards = "".join(card(p) for p in posts)

    # ---- 首页 ----
    cols_html = "".join(
        f'<a class="card" href="columns.html#c-{c["id"]}">'
        f'<div class="cname">{c["name"]}</div>'
        f'<div class="cmeta">{H.escape(c.get("note",""))}</div></a>' for c in columns)
    open(f"{out}/index.html", "w", encoding="utf-8").write(f"""<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{site['name']} · {site['tagline']}</title>
<meta name="description" content="{site['description']}">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate, max-age=0">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
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
<b>最后更新：{BUILD_HUMAN}</b>（北京时间）· 每天 12:10 自动跑批<br>
<span style="color:var(--ink3)">若看到旧内容，点上方「↻ 强制刷新」，或用 Ctrl/Cmd + Shift + R 硬刷新。</span>
</div>
<h2>最新精读</h2>
<div class="cards">{cards}</div>
<h2>全部栏目</h2>
<div class="cards">{cols_html}</div>
<footer>每天 12:10 自动更新 · 论文原文版权归原作者所有<br>最后更新：{BUILD_HUMAN}</footer>
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
{nav('cols')}<div class="wrap">
<header class="top"><div class="kicker">全部栏目</div><h1>按领域浏览</h1>
<p style="color:var(--ink2)">一篇论文可能同时属于多个领域。每栏独立成页，交叉内容以交叉标签呈现。</p>
</header>{sec}<footer>CtrlView · 最后更新 {BUILD_HUMAN}</footer></div></body></html>""")

    # ---- 归档页 ----
    open(f"{out}/archive.html", "w", encoding="utf-8").write(f"""<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>全部文章 · CtrlView</title>
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<link rel="stylesheet" href="{CSSFILE}?v={BUILD}"></head><body>
{nav('arch')}<div class="wrap wide">
<header class="top"><div class="kicker">全部文章</div><h1>归档（{len(posts)} 篇）</h1></header>
<div class="cards">{cards}</div><footer>CtrlView · 最后更新 {BUILD_HUMAN}</footer></div></body></html>""")

    print(f"OK  {len(posts)} 篇精读 -> {out}")
    for p in posts:
        print(f"   {p['id']}  {p['fm'].get('title','')[:46]}")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
