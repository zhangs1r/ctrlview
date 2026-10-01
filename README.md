# CtrlView

用控制工程的视角读 AI 与机器人论文。

面向控制工程专业背景、但 AI/机器人是入门的读者：每篇论文讲清
问题背景、核心公式与设计动机，术语第一次出现必解释，并用控制概念做类比。

**成功标准只有一条**：一个没读过原文的人，读完这篇精读，能复述出论文的核心方法与思路。
不是"能不能复现"——想复现的人自然会回去啃原文。

## 结构

- `posts/*.md` — 精读正文（front-matter + Markdown + 内联 LaTeX）
- `pipeline/prompts/` — 精读提示词：`L0-精读契约.md` 是站点级契约，`L1-<栏目>.md` 是七个栏目各自的 profile；`README.md` 是每周跑批的运行手册
- `pipeline/` — 生成脚本（fetch_new / record_round / build_site / check_quality / extract_figs）
- `figs/` — 插图。论文原图与编者绘制的示意图都在这里，**文件名前缀必须是 arXiv 编号**，否则两篇都有"图 2"时会互相覆盖
- `data/history.json` — **每周推荐记录，也是去重的权威来源**
- `data/seen.json` — 由 history.json 派生，保留仅为兼容旧接口
- `data/queue.json` / `candidates.json` — 抓取产物，不入库
- `docs/` — 生成产物（入库，由 Pages 直接发布该目录）

## 流水线

```
fetch_new.py . 9      抓 arXiv 各栏目候选，自动剔除历史推荐 → data/queue.json
（每栏目挑 3 篇）      按 L1 栏目 profile 的选文偏好挑
record_round.py       登记本轮，重复直接拒绝 → data/history.json
（下载原文）           paper-download 技能的 fetch_paper.py，内置 %PDF- 魔数校验
（解析）               PDF 必须走 MinerU 转 Markdown 才能读
（writer 出稿）        posts/<arxiv_id>.md
check_quality.py      文风门禁，必须 exit 0
build_site.py . docs  → docs/*.html（首页 / 栏目 / 主题 / 术语表 / 搜索 / 历史 / 归档 / feed.xml）
git push              → GitHub Pages 自动重建
```

写作流程、硬前提和十二条内容规则都在 `pipeline/prompts/L0-精读契约.md`。
**盲读评审目前关闭**，开启方式和开关位置见该文件第九节。

## 站点页面

| 页面 | 内容 |
|---|---|
| `index.html` | 最新精读 + 全部栏目 |
| `columns.html` | 按七个栏目分组 |
| `topics.html` | 按标签聚合的**主题页**，自动生成 |
| `glossary.html` | **跨文章术语表**，汇总每篇末尾的「名词速查」 |
| `search.html` | **站内搜索**，索引内联在页面里，不联网也能用 |
| `history.html` | **每周推荐记录**，也是去重的依据 |
| `archive.html` | 全部文章 |
| `feed.xml` | **Atom 订阅** |

这些页面都是构建时从 `posts/` 和 `data/` 自动生成的，不需要手工维护。
精读里新出现的术语会自动进术语表，新标签会自动开主题页。

`data/relations.json` 记录每篇最接近的几项工作（带 arXiv 编号的会自动变成站内链接）；
正文互相提及的精读由构建脚本自动互相链上。

## 定时任务

每周一 18:00，每栏目精读 3 篇，全站 21 篇。执行器是本机 DSH 任务看板。
整条链路**不需要代理**（arXiv PDF、OpenAlex、MinerU 都直连可用），
只有最后 push 到 GitHub 那一步要开。

## 不重复推的保证

三层拦截：

1. `fetch_new.py` 在抓取阶段就剔除历史论文，候选池里不会出现重复
2. 挑选阶段要求给出"为什么选它、哪几篇压后"的理由，可人工复核
3. `record_round.py` 在登记阶段再查一次，命中历史直接 exit 1

## 缓存

GitHub Pages 的 CDN 对所有文件下发 `cache-control: max-age=600`（Fastly varnish），
浏览器与 CDN 都可能缓存 10 分钟。本站用三层对策：

1. HTML 内嵌 `<meta http-equiv="Cache-Control" no-store">`（管浏览器）
2. CSS / 图片用**内容指纹 + 构建时间戳**（内容变则 URL 变，CDN 必回源）
3. 导航常驻「↻ 强制刷新」入口（重新拉取**当前页**），页脚与首页显示精确构建时间

## 已知坑

- 脚本**不要放在 `%TEMP%` 里跑**。那里有一个 `struct.py`，脚本目录会被插到 `sys.path`
  最前面，`zipfile` 会导入到假的 `struct`，`latex2mathml` 直接崩，公式静默降级成源码。
- `check_quality.py` 在 GBK 控制台打印 `✓` 会崩，跑之前先 `$env:PYTHONIOENCODING = "utf-8"`。
- `tags` 要写成逗号分隔、不带方括号和引号，否则页面上会显示出引号。

## 许可

代码 MIT。论文版权归原作者所有，本站仅做导读与图引用。
