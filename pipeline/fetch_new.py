#!/usr/bin/env python3
"""抓取各栏目当天的候选论文，输出待精读清单（JSON）。

只负责「发现」，不负责「写精读」——精读由 LLM 在下一步做。
去重靠 data/seen.json（已处理过的 arXiv ID）。
"""
import json, os, re, sys, time, urllib.request, urllib.parse, datetime, glob

API = "https://export.arxiv.org/api/query"
UA = "ctrlview-fetch/1.0"


def fetch(query, max_results=30, window_days=2):
    """手工拼 query string —— urlencode 会破坏 arXiv 的引号语义（见 skill 记录）。"""
    d1 = datetime.date.today()
    d0 = d1 - datetime.timedelta(days=window_days)
    q = f'{query} AND submittedDate:[{d0:%Y%m%d}0000 TO {d1:%Y%m%d}2359]'
    url = f'{API}?search_query={urllib.parse.quote(q, safe=":[]")}&max_results={max_results}&sortBy=submittedDate&sortOrder=descending'
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                x = r.read().decode("utf-8", "ignore")
            return parse(x)
        except Exception as e:
            if i == 2:
                print(f"  ! 查询失败 {query}: {e}", file=sys.stderr)
            time.sleep(4)
    return []


def parse(xml):
    out = []
    for m in re.finditer(r"<entry>(.*?)</entry>", xml, re.S):
        e = m.group(1)
        aid = re.search(r"<id>http[s]?://arxiv\.org/abs/([^<]+)</id>", e)
        ti = re.search(r"<title>(.*?)</title>", e, re.S)
        su = re.search(r"<summary>(.*?)</summary>", e, re.S)
        au = re.findall(r"<name>(.*?)</name>", e)
        if not (aid and ti):
            continue
        pid = aid.group(1).split("v")[0]
        out.append({
            "id": pid,
            "title": re.sub(r"\s+", " ", ti.group(1)).strip(),
            "abstract": re.sub(r"\s+", " ", su.group(1)).strip() if su else "",
            "authors": au[:6],
            "pdf": f"https://arxiv.org/pdf/{pid}",
        })
    return out


def main(repo):
    cfg = json.load(open(f"{repo}/pipeline/columns.json", encoding="utf-8"))
    seen_p = f"{repo}/data/seen.json"
    seen = set(json.load(open(seen_p))) if os.path.exists(seen_p) else set()

    found = {}
    for c in cfg["columns"]:
        got, ids = [], set()
        for q in c["queries"]:
            for p in fetch(q):
                if p["id"] in seen or p["id"] in ids:
                    continue
                ids.add(p["id"])
                p["column"] = c["id"]
                p["column_name"] = c["name"]
                got.append(p)
            time.sleep(3.2)          # arXiv 要求 >=3s 间隔
        found[c["id"]] = got
        print(f"{c['name']:20} 候选 {len(got)}")

    os.makedirs(f"{repo}/data", exist_ok=True)
    json.dump(found, open(f"{repo}/data/candidates.json", "w"),
              ensure_ascii=False, indent=1)

    # 按栏目均衡取样：每栏最多 PER_COL 候选，保证小栏目不被大栏目挤掉
    PER_COL = 8
    fresh, seen2 = [], set()
    for c in cfg["columns"]:
        ps = sorted(found.get(c["id"], []), key=lambda x: x["id"], reverse=True)
        for p in ps[:PER_COL]:
            if p["id"] in seen2:
                continue
            seen2.add(p["id"])
            fresh.append(p)
    # 同栏目内按 id 倒序（数字比较，避免字符串排序把大 id 排后面）
    fresh.sort(key=lambda x: (x["column"], x["id"]), reverse=False)
    fresh.sort(key=lambda x: int(x["id"].split(".")[-1]) if x["id"].split(".")[-1].isdigit() else 0,
               reverse=True)

    total = sum(len(v) for v in found.values())
    json.dump(fresh, open(f"{repo}/data/queue.json", "w"),
              ensure_ascii=False, indent=1)
    import collections
    dist = collections.Counter(x["column_name"] for x in fresh)
    print(f"\n合计候选 {total}，去重后入队 {len(fresh)}（已跳过历史 {len(seen)} 篇）")
    print("入队分布：", dict(dist))
    print("→ data/queue.json 是下一步精读要处理的清单")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
