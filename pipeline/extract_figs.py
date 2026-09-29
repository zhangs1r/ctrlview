#!/usr/bin/env python3
"""从论文 PDF 提取图表区域（矢量图靠整页渲染+裁切，位图靠 pdfimages）。

思路：
1) pdftotext 全文 + 定位每个 "Figure N:" 图题在第几页
2) 该页用 pdftoppm 高 DPI 渲染 → 从图题上方往上裁出图区
3) 裁剪范围用启发式：图题上方连续的非文本行。简化为按比例裁剪。
输出: figs.json {fig_no: {page, bbox, path, caption}}
"""
import subprocess, re, sys, os, json, glob
from PIL import Image

DPI = 150
SCALE = DPI / 72.0


def page_texts(pdf, npages):
    out = {}
    for p in range(1, npages + 1):
        t = subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), pdf, "-"],
                           capture_output=True, text=True).stdout
        out[p] = t
    return out


def render(pdf, page, dpi=DPI):
    prefix = f"/tmp/_pg{page}"
    for f in glob.glob(prefix + "*.png"):
        os.remove(f)
    subprocess.run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(dpi), "-png", pdf, prefix],
                   capture_output=True)
    g = glob.glob(prefix + "*.png")
    return g[0] if g else None


def find_captions(texts):
    """返回 {fig_no: page}"""
    caps = {}
    for p, t in texts.items():
        for m in re.finditer(r"Figure\s+(\d+)\s*[:.]", t):
            caps.setdefault(int(m.group(1)), p)
    return caps


def crop_below_caption(img, caption_frac=0.30):
    """从页面顶部裁到图题上方:图通常在页顶。启发式裁前 55%。"""
    w, h = img.size
    return img.crop((int(w * 0.06), int(h * 0.05), int(w * 0.94), int(h * 0.05 + h * caption_frac)))


if __name__ == "__main__":
    pdf = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else "figs"
    os.makedirs(outdir, exist_ok=True)
    npages = int(subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
                 .split("Pages:")[1].split()[0])
    texts = page_texts(pdf, npages)
    caps = find_captions(texts)
    print(f"pages={npages} captions={caps}")
    meta = []
    for fig, page in sorted(caps.items()):
        p = render(pdf, page)
        if not p:
            continue
        img = Image.open(p)
        c = crop_below_caption(img)
        fp = f"{outdir}/fig{fig:02d}.png"
        c.save(fp)
        meta.append({"fig": fig, "page": page, "path": fp,
                     "size": c.size,
                     "caption": re.search(rf"Figure\s+{fig}\s*[:.]([^\n]*(?:\n(?!\s*\n)[^\n]*){{0,3}})",
                                          texts[page]).group(0)[:400] if re.search(rf"Figure\s+{fig}\s*[:.]", texts[page]) else ""})
        print(f"  Fig{fig} p{page} -> {fp} {c.size}")
        os.remove(p)
    json.dump(meta, open(f"{outdir}/figs.json", "w"), ensure_ascii=False, indent=1)
