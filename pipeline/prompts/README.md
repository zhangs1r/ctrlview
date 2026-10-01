# 精读流水线的提示词与运行手册

## 文件

| 文件 | 作用 |
|---|---|
| `L0-精读契约.md` | 站点级契约：格式、骨架、文风禁令、12 条内容规则、盲读考卷、两轮制流程 |
| `L1-<栏目>.md` | 栏目 profile：必读项、可压缩项、类比库、选文偏好。七个栏目各一份 |
| `../record_round.py` | 登记一轮推荐，并守住「不重复推」的闸门 |
| `../check_quality.py` | 文风门禁，必须 exit 0 |
| `../build_site.py` | 构建站点，检查公式有没有降级 |

## 每周跑批的运行手册

定时任务：**每周一 18:00**。每栏目精读 **2 篇**，全站 14 篇。

### 第 0 步 · 环境

```powershell
$env:PYTHONIOENCODING = "utf-8"   # 否则中文输出会乱码
```

不需要代理。arXiv 的 PDF 端点、OpenAlex、MinerU 都是直连可用。
**只有最后 push 到 GitHub 那一步需要开代理**（clash-proxy 技能里有开关脚本）。

### 第 1 步 · 抓候选（自动去重）

```powershell
python pipeline\fetch_new.py .
```

**窗口 = 上一轮登记的日期 + 1 天 → 今天**，不是固定天数。脚本读 `data/history.json`
里最新一轮的 `date`，从它后面一天开始收，收到今天为止，然后：

- 把**任何历史轮次里出现过的论文全部剔除**（去重的权威来源就是 `history.json`）
- 窗口内**全量收取**（分页抓，不截断），全部写进 `data/queue.json`
- 结尾打印**逐日覆盖度自检**，哪一天没有候选会显式列出来

不要改回「按提交时间倒序取最新 N 条」的写法。老版本每个查询只取最新 30 条，
一周有几百篇的高频查询（`cat:cs.RO`、`cat:eess.SY`）30 条全落在最后一天，
9 天窗口实际退化成约 3 天、八成集中在一个日子，早几天提交的论文根本没进过候选池。

想临时改窗口或限量时：

```powershell
python pipeline\fetch_new.py . 9              # 覆盖窗口为最近 9 天
python pipeline\fetch_new.py . --per-col 40   # 每栏目入队上限（默认不截断）
```

### 第 2 步 · 每栏目挑 2 篇（先分诊打分，再挑）

候选池一周有几百到上千篇，逐篇贴摘要既看不完也不可复核，所以这一步走
**分诊 → 打分 → 排序**，三个产物都留在 `data/` 里可以倒查。

```powershell
# ① 分诊：粗筛 + 机械预排序，生成每栏短名单（默认 20 篇，带完整摘要）
python pipeline\triage.py . --top 20
```

`triage.py` 只做机械的事：用 `pipeline/rubric.json` 里该栏目的**核心词**过一道相关性闸门，
再按正负信号（真机、野外、失败案例、定理 / 仅仿真、综述…）做一个**预排序分**，
决定先看谁的摘要。这个预排序分**不是**评分表的分数。

产物 `data/triage/<column>.json` 把候选池三份账算平，不会有论文悄悄消失：

| 段 | 内容 |
|---|---|
| `shortlist` | 进短名单的，带**完整摘要**和空评分位，只对这些打分 |
| `rest` | 相关但排在短名单之外的，只有 id 和标题（想多看就调大 `--top`） |
| `offtopic` | 核心词一个都没命中的，只有 id 和标题，**没有丢弃**，可人工捞回 |

```powershell
# ② 打分：读 shortlist 里的完整摘要，照 rubric.json 的 guide 逐项填 0/1/2
#    （直接编辑 data/triage/<column>.json 的 scores 字段）

# ③ 排序：校验有没有漏打分，加权算总分，输出建议
python pipeline\triage.py . --rank --pick 2
```

判据全部取自 `L1-<栏目>.md` 的「必读项」与「选文偏好」，不另立标准；每条判据的
权重和 0/1/2 的分档口径写在 `pipeline/rubric.json` 的 `guide` 里。**摘要里判不出的
必读项一律给 0，不要猜**——那部分留给精读阶段。排序结果写到 `data/triage-ranked.md`。

挑完把结果写成 `data/picks.json`：

```json
[
  {"id": "2609.12345", "column": "slam", "title": "论文标题"},
  {"id": "2609.23456", "column": "slam", "title": "..."}
]
```

登记时**备注里写明各栏总分与压后理由**，这样"为什么选它"是可复核的。
然后登记（这一步会再查一次重复，重复就拒绝）。**日期写实际执行那一天**，
窗口就是按这个日期推算的，写错会让下一轮的窗口跑偏：

```powershell
python pipeline\record_round.py . 2026-W42 2026-10-08 data\picks.json "备注"
```

### 第 3 步 · 逐篇精读（当前为单轮，盲读评审已关闭）

**硬前提：必须下载原文；下载到的是 PDF 就必须先用 MinerU 解析成 Markdown 再读。**
只用摘要或记忆写精读是不允许的——摘要里没有方法细节，记忆会编出不存在的公式和数字。
完整约束见 `L0-精读契约.md` 第二节。

**当前流程**：writer 出稿 → 过门禁 → 交稿。写作时自己按 L0 第六节的十二条规则自查。

**盲读评审已关闭**。需要时再开，开关在这三处，要一起改：
本文件这一段、`L0-精读契约.md` 第九节、任务看板上那条定时任务的 prompt。

下载与解析：

```powershell
# 下载（走 paper-download 技能，内置 %PDF- 魔数校验）
python "$env:USERPROFILE\.dsh\skills\paper-download\scripts\fetch_paper.py" manifest.json

# 解析（MinerU，token 要从注册表回填）
foreach ($s in @('User','Machine','Process')) {
  $t = [Environment]::GetEnvironmentVariable('MINERU_API_TOKEN', $s)
  if ($t) { $env:MINERU_API_TOKEN = $t; break }
}
python "$env:USERPROFILE\.agents\skills\mineru-pdf-reader\scripts\convert_pdf.py" `
       "<PDF>" "<输出目录>"
```

**脚本不要放在 `%TEMP%` 里跑**。那里有一个 `struct.py`，脚本目录会被插到
`sys.path` 最前面，`zipfile` 会导入到假的 `struct`，`latex2mathml` 直接崩，
公式会静默降级成源码。

### 第 4 步 · 门禁与构建

```powershell
python pipeline\check_quality.py posts\<编号>.md
python "%USERPROFILE%\.agents\skills\human-writing\scripts\check_prose.py" posts\<编号>.md
python pipeline\build_site.py . docs
```

构建输出里出现 `⚠ 有 N 处公式转换失败` 就是 LaTeX 写错了，修到 0。
构建脚本本身报错时 exit code 不是 0，**先看 exit code 再看别的**——只 grep
「公式转换失败」会漏掉真正的崩溃（曾经把首页改造引发的 `UnboundLocalError` 漏过去，
归档页被写成 0 字节还误判成构建成功）。

构建会自动重生成：首页、栏目页、主题页、术语表、搜索、历史、全部文章、Atom 订阅。

**首页只显示最新一轮推荐**（读 `data/history.json` 里 date 最大的那一轮，按栏目分组，
卡片带摘要）；往期的精读留在「全部文章」「栏目页」，每一轮的推荐记录在「历史推荐」。
所以首页不需要手工维护，但**不要让轮次日期失真**，否则首页会指向错误的"本轮"。

### 第 5 步 · 发布

开代理，提交并推送。GitHub Pages 会自动重建。

## 去重是怎么保证的

三层：

1. `fetch_new.py` 在抓取阶段就把历史论文剔除，候选池里根本不会出现重复
2. 挑选阶段要求给出"为什么选它"，人工可复核
3. `record_round.py` 在登记阶段再查一次，重复直接 exit 1

`data/history.json` 是唯一的权威来源。`data/seen.json` 由它派生，保留只是为了
兼容旧接口。
