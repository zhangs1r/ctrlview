# CtrlView

用控制工程的视角读 AI 与机器人论文。

面向控制工程专业背景、但 AI/机器人是入门的读者：每篇论文讲清
问题背景、核心公式与设计动机，术语第一次出现必解释，并用控制概念做类比。

## 结构
- `posts/*.md` — 精读正文（front-matter + Markdown + MathML-ready LaTeX）
- `pipeline/` — 生成脚本（fetch_new / render / build_site / check_quality）
- `figs/` — 从论文 PDF 提取的插图
- `data/` — seen.json 已处理列表，queue.json 待处理队列
- `out/` — 生成产物（不入库，由 Pages 发布）

## 流水线
```
fetch_new.py   抓 arXiv 各栏目候选 → data/queue.json
（LLM 写精读）  → posts/<arxiv_id>.md
check_quality.py  AI 味自检，超阈值 exit 1
build_site.py  → out/*.html
git push       → GitHub Pages 自动重建
```

## 缓存
GitHub Pages 的 CDN 对所有文件下发 `cache-control: max-age=600`（Fastly varnish），
浏览器与 CDN 都可能缓存 10 分钟。本站用三层对策：
1. HTML 内嵌 `<meta http-equiv="Cache-Control" no-store">`（管浏览器）
2. CSS / 图片用**内容指纹 + 构建时间戳**（内容变则 URL 变，CDN 必回源）
3. 导航常驻「↻ 强制刷新」入口，页脚与首页显示精确构建时间

## 许可
代码 MIT。论文版权归原作者所有，本站仅做导读与图引用。
