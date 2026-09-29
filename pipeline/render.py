#!/usr/bin/env python3
"""把精读 Markdown 渲染为响应式单页 HTML（图片内嵌 base64）。"""
import re, base64, json, sys, os, html as H

CSS = """
:root{
  --bg:#fbfaf8; --card:#fff; --ink:#1b1b1f; --ink2:#4a4a55; --ink3:#8a8a96;
  --line:#e6e4df; --accent:#2d5f8a; --accent-bg:#eef4f9; --ctrl:#8a5a2d; --ctrl-bg:#fdf5ec;
  --code:#f4f2ee; --maxw:740px;
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
.wrap{max-width:var(--maxw);margin:0 auto;padding:0 20px 96px}
header.top{padding:52px 0 28px;border-bottom:1px solid var(--line);margin-bottom:34px}
.kicker{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);font-weight:700}
h1{font-size:clamp(26px,5.2vw,38px);line-height:1.24;margin:14px 0 12px;letter-spacing:-.02em}
.meta{color:var(--ink3);font-size:14px;line-height:1.9}
.meta b{color:var(--ink2);font-weight:600}
.tags{margin-top:14px;display:flex;flex-wrap:wrap;gap:7px}
.tag{font-size:12px;padding:4px 11px;border-radius:99px;background:var(--accent-bg);color:var(--accent);font-weight:600}
h2{font-size:clamp(19px,3.4vw,23px);margin:52px 0 16px;padding-top:16px;border-top:1px solid var(--line);letter-spacing:-.01em}
h3{font-size:17px;margin:30px 0 10px;color:var(--ink)}
p{margin:15px 0}
ul,ol{padding-left:24px;margin:15px 0}
li{margin:8px 0}
a{color:var(--accent)}
strong{font-weight:680}
hr{border:0;border-top:1px solid var(--line);margin:40px 0}
blockquote{margin:22px 0;padding:14px 20px;background:var(--card);border-left:3px solid var(--accent);
  border-radius:0 8px 8px 0;color:var(--ink2)}
blockquote p{margin:6px 0}
figure{margin:28px 0}
figure img{width:100%;height:auto;display:block;border:1px solid var(--line);border-radius:10px;background:#fff}
figcaption{margin-top:11px;font-size:13.5px;line-height:1.7;color:var(--ink3)}
figcaption b{color:var(--ink2)}
aside.ctrl{margin:24px 0;padding:15px 18px;background:var(--ctrl-bg);border-left:3px solid var(--ctrl);
  border-radius:0 8px 8px 0;font-size:15.5px;line-height:1.75}
aside.ctrl b{color:var(--ctrl);display:block;margin-bottom:4px;font-size:12.5px;letter-spacing:.08em;text-transform:uppercase}
table{width:100%;border-collapse:collapse;margin:20px 0;font-size:14.5px}
th,td{padding:9px 11px;border-bottom:1px solid var(--line);text-align:left}
th{font-weight:680;color:var(--ink2);font-size:13px;letter-spacing:.03em;text-transform:uppercase;
   background:var(--card)}
td:first-child{font-weight:600}
tr:last-child td{border-bottom:none}
table tr.hl td{background:var(--accent-bg);color:var(--accent);font-weight:700}
pre{background:var(--code);padding:15px 18px;border-radius:9px;overflow-x:auto;font-size:14px;
    font-family:ui-monospace,SFMono-Regular,Menlo,monospace;line-height:1.65;margin:18px 0;border:1px solid var(--line)}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.9em;background:var(--code);
     padding:2px 6px;border-radius:4px}
pre code{background:none;padding:0}
pre.flow{background:var(--code);border-left:3px solid var(--accent);font-size:13.5px;
  line-height:2;white-space:pre;overflow-x:auto;padding:16px 18px}
.eq{position:relative;margin:24px 0;padding:18px 52px;background:var(--card);
  border:1px solid var(--line);border-radius:10px;overflow-x:auto}
.eq .eqn{position:absolute;right:14px;top:50%;transform:translateY(-50%);
  font-size:12.5px;color:var(--ink3);font-weight:600;background:var(--bg);
  padding:2px 7px;border-radius:5px;border:1px solid var(--line)}
.eq math{font-size:1.02em;display:block;overflow-x:auto;overflow-y:hidden}
.eq math[display=inline]{display:inline}
@media(max-width:600px){pre.flow{font-size:12px;padding:13px 14px;line-height:1.9}}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.warn{background:rgba(190,80,40,.09);border-left:3px solid #b85028;padding:13px 17px;border-radius:0 8px 8px 0;margin:20px 0}
.end{margin-top:56px;padding-top:26px;border-top:2px solid var(--line);font-size:15.5px;color:var(--ink2)}
footer{color:var(--ink3);font-size:13px;text-align:center;padding:34px 0 0}
@media(max-width:600px){
  body{font-size:16.5px} .wrap{padding:0 16px 64px} header.top{padding:34px 0 22px}
  table{font-size:13.5px} th,td{padding:7px 8px}
  pre{padding:12px 14px;font-size:13px}
  aside.ctrl{font-size:15px}
}
"""


def img64(path):
    d = open(path, "rb").read()
    return "data:image/png;base64," + base64.b64encode(d).decode()


def inline_math(md):
    # $$...$$ -> 渲染为块级（本站用 MathML/纯文本，样张直接显示 LaTeX 源码）
    return md


def md2html(md, imgsrc):
    out, i = [], 0
    lines = md.split("\n")

    # 剥离 front-matter（必须在任何渲染之前整体处理）
    if lines and lines[0].strip() == "---":
        for k in range(1, len(lines)):
            if lines[k].strip() == "---":
                lines = lines[k + 1:]
                break

    while i < len(lines):
        ln = lines[i]
        s = ln.strip()

        # figure <figure src= caption=>...</figure>
        m = re.match(r'^<figure\s+src="([^"]+)"\s+caption="([^"]*)">', s)
        if m:
            src, cap = m.group(1), H.unescape(m.group(2))
            body = "\n".join(lines[i + 1:])
            fm = re.search(r"<figcaption>(.*?)</figcaption>", body, re.S)
            fc = fm.group(1) if fm else cap
            img = re.sub(r"<[^>]+>", "", fc).strip()
            img = re.sub(r"\s+", " ", H.unescape(img))
            out.append(
                f'<figure><img src="{os.path.basename(imgsrc)}" alt="论文插图" loading="lazy" decoding="async">'
                f"<figcaption>{fc}</figcaption></figure>")
            # skip until </figure>
            while i < len(lines) and "</figure>" not in lines[i]:
                i += 1
            i += 1
            continue

        # aside ctrl
        if s.startswith("<aside"):
            blk = []
            while i < len(lines) and "</aside>" not in lines[i]:
                blk.append(lines[i].strip())
                i += 1
            i += 1
            inner = " ".join(x for x in blk if x)
            inner = re.sub(r"</?b>", lambda m: "<strong>" if ">" not in m.group(0) else "</strong>", inner)
            out.append(f"<aside class='ctrl'>{inner}</aside>")
            continue

        # headings
        if s.startswith("### "):
            out.append(f"<h3>{H.escape(s[4:])}</h3>"); i += 1; continue
        if s.startswith("## "):
            out.append(f"<h2>{H.escape(s[3:])}</h2>"); i += 1; continue
        if s.startswith("# "):
            out.append(f"<h1>{H.escape(s[2:])}</h1>"); i += 1; continue

        # hr
        if s in ("---", "***", "___"):
            out.append("<hr>"); i += 1; continue

        # blockquote
        if s.startswith(">"):
            blk = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                blk.append(lines[i].strip().lstrip(">").strip()); i += 1
            out.append("<blockquote><p>" + inline_md(" ".join(x for x in blk if x)) + "</p></blockquote>")
            continue

        # warn
        if s.startswith("⚠"):
            out.append(f'<div class="warn">{cell_md(s.replace("⚠", "", 1).strip())}</div>')
            i += 1
            continue

        # table
        if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            hdr = [x.strip() for x in s.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([x.strip() for x in lines[i].strip().strip("|").split("|")])
                i += 1
            th = "".join(f"<th>{H.escape(x)}</th>" for x in hdr)
            tb = ""
            for r in rows:
                cls = ""
                if r and ("本文" in r[0] or "InfiniHand" in r[0]):
                    cls = " class='hl'"
                tds = "".join(f"<td>{cell_md(x)}</td>" for x in r)
                tb += f"<tr{cls}>{tds}</tr>"
            out.append(f'<div class="scroll"><table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div>')
            continue

        # 代码块 ```
        if s.startswith("```"):
            i += 1
            blk = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                blk.append(lines[i])
                i += 1
            i += 1
            code = H.escape("\n".join(blk))
            out.append(f'<pre class="flow"><code>{code}</code></pre>')
            continue

        # display math $$...$$（多行或单行都支持）
        if s.startswith("$$"):
            if s.count("$$") >= 2 and len(s.strip()) > 4:      # 单行闭合
                body, i = s[2:].split("$$", 1)[0], i + 1
            else:                                              # 多行
                blk, i = [], i + 1
                while i < len(lines) and "$$" not in lines[i]:
                    blk.append(lines[i].strip())
                    i += 1
                body = "\n".join(blk)
                i += 1
            num = _eqnum(body)
            latex = re.sub(r"\\tag\{[^}]*\}", "", body).strip()
            out.append(f'<div class="eq"><span class="eqn">{num}</span>'
                       f'{tex(latex, display=True)}</div>')
            continue

        # inline math $...$
        if re.search(r"\$[^$]+\$", s):
            rest = inline_md(s)
            def _im(mm):
                return tex(mm.group(1), display=False)
            out.append("<p>" + re.sub(r"\$([^$]+)\$", _im, rest) + "</p>")
            i += 1
            continue

        # list
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
            lis = "".join(f"<li>{inline_md(x)}</li>" for x in items)
            out.append(f"<{tag}>{lis}</{tag}>")
            continue

        if not s:
            i += 1
            continue

        out.append(f"<p>{inline_md(s)}</p>")
        i += 1
    return "\n".join(out)


def tex(latex, display=False):
    """LaTeX -> MathML。沙箱内 CDN 不可达，用 Python 预渲染成 MathML，浏览器原生支持。"""
    try:
        import latex2mathml.converter as C
        mml = C.convert(latex, display="block" if display else "inline")
        return f'<math xmlns="http://www.w3.org/1998/Math/MathML" display="{"block" if display else "inline"}" class="mm">{mml.split(">", 1)[1] if ">" in mml else mml}</math>'
    except Exception as e:
        return f'<code class="tex-err">{H.escape(latex)}</code>'


def cell_md(s):
    """表格单元：行内格式 + 行内公式"""
    s = H.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    if "$" in s:
        s = re.sub(r"\$([^$]+)\$", lambda m: tex(m.group(1), display=False), s)
    return s


def _eqnum(s):
    """从 \\tag{5} 提取编号，渲染成 (5)"""
    m = re.search(r"\\tag\{([^}]*)\}", s)
    return f"({m.group(1)})" if m else ""


def inline_md(s):
    s = H.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', s)
    return s


def main(mdpath, imgpath, outpath):
    md = open(mdpath, encoding="utf-8").read()
    fm = {}
    if md.startswith("---"):
        parts = md.split("---", 2)
        for ln in parts[1].strip().split("\n"):
            if ":" in ln:
                k, v = ln.split(":", 1)
                fm[k.strip()] = v.strip().strip('"')
    tags = ""
    if "tags" in fm:
        try:
            tags = "".join(f'<span class="tag">{H.escape(t.strip())}</span>'
                           for t in fm["tags"].strip("[]").split(",") if t.strip())
        except Exception:
            pass
    body = md2html(md, imgpath)
    doc = f"""<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{H.escape(fm.get('title','精读'))}</title>
<meta name="description" content="{H.escape(fm.get('title',''))}">
<style>{CSS}</style></head><body><div class="wrap">
<header class="top">
<div class="kicker">{H.escape(fm.get('column',''))} · 论文精读</div>
<h1>{H.escape(fm.get('title',''))}</h1>
<div class="meta">
<b>{H.escape(fm.get('authors',''))}</b><br>
arXiv:{H.escape(fm.get('arxiv',''))} · {H.escape(fm.get('date',''))} · 精读约 {H.escape(fm.get('read_time',''))}
</div>
<div class="tags">{tags}</div>
</header>
{body}
<footer>样张 · 由 hotbot 精读流水线生成</footer>
</div></body></html>"""
    open(outpath, "w", encoding="utf-8").write(doc)
    print(f"OK -> {outpath}  ({len(doc)//1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
