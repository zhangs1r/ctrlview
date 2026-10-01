#!/usr/bin/env python3
"""选文分诊：把一周几百篇候选压成「值得读摘要的短名单」，再按评分表排座次。

两步走（对应 pipeline/prompts/README.md 第 2 步）：

  第一遍 粗筛 —— 用栏目核心词做相关性闸门，标题和摘要里一个核心词都不沾的**不丢弃**，
      只是排在短名单之外，写进产物的 offtopic 段，附上 id 和标题方便人工捞回。
      核心词表宁可放宽：实测把 quadruped/legged/locomotion 这类词漏掉，会直接把
      「四足跑酷」这类明显属于机器人栏目的论文筛出去，那正是要避免的事。
  第二遍 打分 —— 对留下来的短名单打**机械预排序**（正负信号计数），
      只用来决定先看谁的摘要，**不是**评分表的分数。
      真正的分数由人/agent 读完整摘要后，照 pipeline/rubric.json 的判据逐项填 0/1/2。

产物：
  data/triage/<column>.json    短名单 + 空评分位（填完分回写同一文件）
  data/triage-ranked.md        --rank 生成：加权总分排序 + 建议选哪几篇

用法:
  python pipeline/triage.py <repo> [--top 20] [--column slam] [--keep-all]
  python pipeline/triage.py <repo> --rank [--pick 2]
"""
import argparse
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# 机械预排序用的信号词。只影响「先看谁」，不影响评分表的分数。
POS = [
    r"real[- ]world", r"real robot", r"onboard", r"field experiment", r"deployed",
    r"hardware", r"we collect", r"dataset collected", r"physical experiment",
    r"failure case", r"failures?", r"degrad", r"ablation", r"open[- ]source",
    r"code (is )?(publicly )?available", r"theorem", r"proof", r"guarantee",
    r"convergence", r"observab", r"benchmark.*real",
]
NEG = [
    r"only in simulation", r"simulation[- ]only", r"purely synthetic", r"synthetic data only",
    r"without real", r"survey", r"position paper",
]


def load_rubric():
    return json.load(open(os.path.join(HERE, "rubric.json"), encoding="utf-8"))


def signals(text):
    pos = sorted({p for p in POS if re.search(p, text, re.I)})
    neg = sorted({p for p in NEG if re.search(p, text, re.I)})
    return pos, neg


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def cmd_shortlist(repo, top, only_col, keep_all):
    rub = load_rubric()
    q = json.load(open(f"{repo}/data/queue.json", encoding="utf-8"))
    outdir = f"{repo}/data/triage"
    os.makedirs(outdir, exist_ok=True)

    by_col = {}
    for p in q:
        by_col.setdefault(p["column"], []).append(p)

    print(f"候选总数 {len(q)}，覆盖 {len(by_col)} 个栏目\n")
    for cid, meta in rub["columns"].items():
        if only_col and cid != only_col:
            continue
        cands = by_col.get(cid, [])
        core = [k.lower() for k in meta["core"]]
        kept, offtopic = [], []
        for p in cands:
            text = (p.get("title", "") + " " + p.get("abstract", ""))
            hit = [k for k in core if k in text.lower()]
            if not hit and not keep_all:
                # 不静默丢弃：写进 offtopic 段，只是不进短名单，人工可以捞回
                offtopic.append({"id": p["id"], "title": p.get("title", ""),
                                 "published": p.get("published", ""),
                                 "reason": "标题与摘要都没有命中栏目核心词"})
                continue
            pos, neg = signals(text)
            p = dict(p)
            p["matched_core"] = hit[:6]
            p["pre_positive"] = pos
            p["pre_negative"] = neg
            p["pre_score"] = 2 * len(pos) - 2 * len(neg) + min(len(hit), 3)
            kept.append(p)

        kept.sort(key=lambda x: (-x["pre_score"], x.get("published", "")))
        short = kept[:top]
        for p in short:
            p["scores"] = {c["id"]: None for c in meta["criteria"]}
            p["note"] = ""
        # 相关但排在短名单之外的，也留 id/标题/预排序分，保证候选池三份账加起来等于总数，
        # 不会有论文既不进短名单、也不在文件里，悄悄消失。
        rest = [{"id": p["id"], "title": p.get("title", ""),
                 "published": p.get("published", ""), "pre_score": p["pre_score"]}
                for p in kept[top:]]

        doc = {
            "column": cid,
            "name": meta["name"],
            "generated": datetime.date.today().isoformat(),
            "candidates_total": len(cands),
            "relevant": len(kept),
            "offtopic": offtopic,
            "rest": rest,
            "shortlist": short,
        }
        path = os.path.join(outdir, f"{cid}.json")
        json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

        print(f"[{meta['name']}]  候选 {len(cands)} = 短名单 {len(short)} + 相关待看 {len(rest)}"
              f" + 核心词未命中 {len(offtopic)}")
        if len(rest):
            print(f"    短名单之外的相关论文 {len(rest)} 篇也在 {path} 的 rest 段（只有 id 和标题，"
                  f"想看得更多就调大 --top）")
        for d in offtopic[:2]:
            print(f"    旁置: {d['id']}  {d['title'][:62]}")
        if len(offtopic) > 2:
            print(f"    …另有 {len(offtopic) - 2} 篇旁置，明细见 {path} 的 offtopic 段（可人工捞回）")
        if len(kept) < top:
            print(f"    ！相关论文只有 {len(kept)} 篇，短名单凑不满 {top}")
        print(f"    短名单 → {path}")
        print(f"    判据: " + " / ".join(f"{c['name']}({c['weight']})" for c in meta["criteria"]))
        print()
    print("下一步：读短名单里的完整摘要，照 rubric.json 的 guide 逐项填 scores（0/1/2），")
    print("        然后 python pipeline/triage.py . --rank")


def cmd_rank(repo, pick, round_id):
    rub = load_rubric()
    outdir = f"{repo}/data/triage"
    if not os.path.isdir(outdir):
        print(f"没有 {outdir}，先跑一次分诊生成短名单")
        return 1
    files = sorted(f for f in os.listdir(outdir) if f.endswith(".json"))
    if not files:
        print(f"{outdir} 里没有短名单文件")
        return 1

    lines = [f"# 选文评分结果（{datetime.date.today().isoformat()}）", ""]
    records = []
    bad = 0
    for fn in files:
        doc = json.load(open(os.path.join(outdir, fn), encoding="utf-8"))
        cid = doc["column"]
        meta = rub["columns"].get(cid)
        if not meta:
            continue
        crit = meta["criteria"]
        scored, pending = [], []
        for p in doc["shortlist"]:
            sc = p.get("scores") or {}
            missing = [c["id"] for c in crit if sc.get(c["id"]) not in (0, 1, 2)]
            if missing:
                pending.append((p, missing))
                continue
            total = sum(sc[c["id"]] / 2.0 * c["weight"] for c in crit)
            scored.append((total, p))
        scored.sort(key=lambda x: -x[0])
        for i, (total, p) in enumerate(scored, 1):
            records.append({"id": p["id"], "column": cid,
                            "title": p.get("title", ""),
                            "total": round(total, 1),
                            "picked": i <= pick,
                            "scores": p["scores"],
                            "note": p.get("note", "")})

        lines += [f"## {meta['name']}（候选 {doc['candidates_total']} → 相关 {doc['relevant']} → 短名单 {len(doc['shortlist'])}）", ""]
        if not scored:
            lines += ["全部短名单还没打分。", ""]
        else:
            head = " | ".join([c["name"] for c in crit])
            lines += [f"| 排名 | 总分 | arXiv | 标题 | {head} |", "|---|---|---|---|" + "---|" * len(crit)]
            for i, (total, p) in enumerate(scored, 1):
                cells = " | ".join(str(p["scores"][c["id"]]) for c in crit)
                mark = " **← 建议选中**" if i <= pick else ""
                lines.append(f"| {i} | {total:.0f} | {p['id']} | {p['title'][:58]}{mark} | {cells} |")
            lines.append("")
            lines.append(f"建议选前 {pick} 篇：" + "、".join(p["id"] for _, p in scored[:pick]))
            lines.append("")
        if pending:
            bad += len(pending)
            lines.append(f"未打分的 {len(pending)} 篇（缺项示例）：")
            for p, missing in pending[:5]:
                lines.append(f"- {p['id']} 缺 {', '.join(missing)}")
            lines.append("")

    path = f"{repo}/data/triage-ranked.md"
    open(path, "w", encoding="utf-8").write("\n".join(lines))
    print(f"排序结果 → {path}")

    # 留档：这个文件很小、可以入库，记录本轮各栏打了多少分、谁被选中。
    # 短名单里是各篇的完整摘要（体积大、每周翻新），放在 data/triage/ 不入库。
    sp = f"{repo}/data/scores.json"
    store = {"note": "每轮选文的评分留档：谁被选中、总分多少、各项分数，用于复核选文过程。"
                     "短名单原文（含完整摘要）在 data/triage/，不入库。",
             "rounds": {}}
    if os.path.exists(sp):
        try:
            store = json.load(open(sp, encoding="utf-8"))
        except (OSError, ValueError):
            pass
    store.setdefault("rounds", {})
    store["rounds"][round_id] = {
        "date": datetime.date.today().isoformat(),
        "pick_per_column": pick,
        "complete": bad == 0,
        "records": records,
    }
    json.dump(store, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"评分留档 → {sp}（轮次 {round_id}，{len(records)} 篇有分）")

    if bad:
        print(f"⚠ 有 {bad} 篇短名单还没填评分，请补齐后再看排名")
        return 1
    print("✓ 所有短名单都已打分")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="选文分诊：粗筛 → 打分 → 排座次")
    ap.add_argument("repo", nargs="?", default=".")
    ap.add_argument("--top", type=int, default=20, help="每栏目短名单长度（默认 20）")
    ap.add_argument("--column", default=None, help="只处理某个栏目 id")
    ap.add_argument("--keep-all", action="store_true", help="跳过相关性粗筛，全部进预排序")
    ap.add_argument("--rank", action="store_true", help="读回已打分的短名单并排序")
    ap.add_argument("--pick", type=int, default=2, help="每栏目选几篇（默认 2）")
    ap.add_argument("--round", default=None, help="轮次 id，写入 data/scores.json（默认今天）")
    a = ap.parse_args()
    if a.rank:
        rid = a.round or datetime.date.today().isoformat()
        sys.exit(cmd_rank(a.repo, a.pick, rid))
    cmd_shortlist(a.repo, a.top, a.column, a.keep_all)
