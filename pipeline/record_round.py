#!/usr/bin/env python3
"""登记一轮推荐：把本周选中的论文写进 data/history.json，并同步 data/seen.json。

用法:
    python pipeline/record_round.py <repo> <轮次id> <日期> <picks.json> [备注]

picks.json 是一个 JSON 数组，每项至少要有 id 和 column:
    [{"id": "2609.27702", "column": "slam", "title": "DAVIO：..."}]

脚本会拒绝已经在任何历史轮次里出现过的 id —— 这是「不重复推」的最后一道闸门，
即使上游挑选时漏了过滤，这里也会拦下来。
"""
import json, os, sys


def main(repo, rid, date, picks_path, note=""):
    hist_p = f"{repo}/data/history.json"
    hist = {"rounds": []}
    if os.path.exists(hist_p):
        hist = json.load(open(hist_p, encoding="utf-8"))
    hist.setdefault("rounds", [])

    # 已有的 id → 出现在哪一轮
    seen = {}
    for r in hist["rounds"]:
        for k in r.get("picks", []):
            seen.setdefault(k["id"], r.get("id", "?"))

    picks = json.load(open(picks_path, encoding="utf-8"))

    dup = [p["id"] for p in picks if p["id"] in seen]
    if dup:
        print("拒绝登记：下面这些论文已经在历史里出现过了")
        for d in dup:
            print(f"  {d}  ← 第 {seen[d]} 轮")
        sys.exit(1)

    # 同一轮内部也不许重复
    ids = [p["id"] for p in picks]
    if len(ids) != len(set(ids)):
        print("拒绝登记：这一轮的 picks 内部有重复 id")
        sys.exit(1)

    if any(r.get("id") == rid for r in hist["rounds"]):
        print(f"拒绝登记：轮次 {rid} 已经存在")
        sys.exit(1)

    hist["rounds"].append({
        "id": rid,
        "date": date,
        "note": note,
        "picks": picks,
    })
    hist["rounds"].sort(key=lambda r: r.get("date", ""))

    json.dump(hist, open(hist_p, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    # seen.json 由 history 派生，保留它是因为 fetch_new 的旧接口还在读
    all_ids = sorted({k["id"] for r in hist["rounds"] for k in r.get("picks", [])})
    json.dump(all_ids, open(f"{repo}/data/seen.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print(f"OK  轮次 {rid}（{date}）登记 {len(picks)} 篇")
    print(f"    累计 {len(hist['rounds'])} 轮 / {len(all_ids)} 篇去重清单 -> {hist_p}")


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4],
         sys.argv[5] if len(sys.argv) > 5 else "")
