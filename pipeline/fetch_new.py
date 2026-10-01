#!/usr/bin/env python3
"""抓取「上一轮跑批之后到今天」的候选论文，输出待精读清单（JSON）。

窗口规则（2026-10-01 改）：
    起点 = data/history.json 里最新一轮的 date + 1 天
    终点 = 今天
窗口**全量收取**，不做「最新优先 + 上限截断」。

为什么改成全量：老版本每个查询只取最新 30 条（sortBy=submittedDate 倒序），
高频查询（cat:cs.RO、cat:eess.SY）一周有几百篇，30 条全落在最后一天，
再叠加 PER_COL 截断，9 天窗口实际退化成约 3 天、且八成集中在一个日子——
早几天提交的好论文根本没进过候选池。现在改为分页把窗口内的结果全部取回，
并在结尾打印**逐日覆盖度**，覆盖不足会显式报警。

去重的权威来源是 data/history.json：出现在任何历史轮次里的论文一律剔除。

用法:
    python pipeline/fetch_new.py <repo>                 # 窗口 = 上轮之后 → 今天
    python pipeline/fetch_new.py <repo> 9               # 覆盖窗口为最近 9 天
    python pipeline/fetch_new.py <repo> --per-col 40     # 每栏目入队上限（默认不截断）
"""
import collections
import datetime
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

API = "https://export.arxiv.org/api/query"
UA = "ctrlview-fetch/1.0"
PAGE = 100            # 分页大小（arXiv 单次上限 2000）
MAX_PER_QUERY = 1500  # 单个查询的安全上限，正常一周远远够用
FALLBACK_DAYS = 7     # 没有历史或上轮日期异常时的兜底窗口


def _get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            if i == tries - 1:
                print(f"  ! 查询失败: {e}", file=sys.stderr)
            time.sleep(4)
    return ""


def parse(xml):
    out = []
    for m in re.finditer(r"<entry>(.*?)</entry>", xml, re.S):
        e = m.group(1)
        aid = re.search(r"<id>http[s]?://arxiv\.org/abs/([^<]+)</id>", e)
        ti = re.search(r"<title>(.*?)</title>", e, re.S)
        su = re.search(r"<summary>(.*?)</summary>", e, re.S)
        pub = re.search(r"<published>([^<]+)</published>", e)
        au = re.findall(r"<name>(.*?)</name>", e)
        if not (aid and ti):
            continue
        pid = aid.group(1).split("v")[0]
        out.append({
            "id": pid,
            "title": re.sub(r"\s+", " ", ti.group(1)).strip(),
            "abstract": re.sub(r"\s+", " ", su.group(1)).strip() if su else "",
            "authors": au[:6],
            "published": pub.group(1)[:10] if pub else "",
            "pdf": f"https://arxiv.org/pdf/{pid}",
        })
    return out


def fetch_all(query, d0, d1):
    """把窗口内的结果分页全部取回。手工拼 query string，
    因为 urlencode 会破坏 arXiv 的引号语义（见 skill 记录）。"""
    q = f'{query} AND submittedDate:[{d0:%Y%m%d}0000 TO {d1:%Y%m%d}2359]'
    out, start = [], 0
    while start < MAX_PER_QUERY:
        url = (f'{API}?search_query={urllib.parse.quote(q, safe=":[]")}'
               f'&start={start}&max_results={PAGE}'
               f'&sortBy=submittedDate&sortOrder=ascending')
        page = parse(_get(url))
        if not page:
            break
        out.extend(page)
        if len(page) < PAGE:
            break
        start += PAGE
        time.sleep(3.2)   # arXiv 要求 >=3s 间隔
    return out


def load_history(repo):
    hist_p = f"{repo}/data/history.json"
    hist = {"rounds": []}
    if os.path.exists(hist_p):
        hist = json.load(open(hist_p, encoding="utf-8"))
    return hist


def pick_window(hist, days=None, today=None):
    """返回 (d0, d1, 说明)。d0/d1 都是 date。"""
    today = today or datetime.date.today()
    if days:
        return today - datetime.timedelta(days=days), today, f"命令行指定最近 {days} 天"
    dates = [r.get("date", "") for r in hist.get("rounds", []) if r.get("date")]
    if not dates:
        return (today - datetime.timedelta(days=FALLBACK_DAYS), today,
                f"没有历史轮次，兜底最近 {FALLBACK_DAYS} 天")
    last = max(datetime.date.fromisoformat(d) for d in dates)
    d0 = last + datetime.timedelta(days=1)
    if d0 > today:
        return (today - datetime.timedelta(days=FALLBACK_DAYS), today,
                f"上一轮日期 {last} 不早于今天，窗口异常，兜底最近 {FALLBACK_DAYS} 天")
    return d0, today, f"上一轮 {last} 之后"


def main(repo, days=None, per_col=0):
    cfg = json.load(open(f"{repo}/pipeline/columns.json", encoding="utf-8"))
    hist = load_history(repo)

    # 去重：只要出现在任何一轮里，后续就不再推。
    # data/seen.json 是旧格式，仍然读进来做兼容（手工标记用）。
    seen = set()
    for r in hist.get("rounds", []):
        for k in r.get("picks", []):
            if k.get("id"):
                seen.add(k["id"])
    seen_p = f"{repo}/data/seen.json"
    if os.path.exists(seen_p):
        seen |= set(json.load(open(seen_p, encoding="utf-8")))

    d0, d1, why = pick_window(hist, days)
    print(f"窗口 {d0} → {d1}（{why}），共 {(d1 - d0).days + 1} 天")

    found, capped = {}, []
    for c in cfg["columns"]:
        got, ids = [], set()
        for q in c["queries"]:
            batch = fetch_all(q, d0, d1)
            for p in batch:
                if p["id"] in seen or p["id"] in ids:
                    continue
                ids.add(p["id"])
                p["column"] = c["id"]
                p["column_name"] = c["name"]
                got.append(p)
            time.sleep(3.2)   # arXiv 要求 >=3s 间隔
        found[c["id"]] = got
        print(f"{c['name']:20} 候选 {len(got)}")

    total = sum(len(v) for v in found.values())
    os.makedirs(f"{repo}/data", exist_ok=True)
    json.dump(found, open(f"{repo}/data/candidates.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # 队列：默认把窗口内全部候选交给挑选环节，不再按「最新 15 条」截断。
    fresh, seen2 = [], set()
    for c in cfg["columns"]:
        ps = sorted(found.get(c["id"], []), key=lambda x: (x.get("published") or "", x["id"]))
        if per_col and len(ps) > per_col:
            capped.append((c["name"], len(ps), per_col))
            ps = ps[-per_col:]      # 截断时保留较新的
        for p in ps:
            if p["id"] in seen2:
                continue
            seen2.add(p["id"])
            fresh.append(p)

    json.dump(fresh, open(f"{repo}/data/queue.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    dist = collections.Counter(x["column_name"] for x in fresh)
    print(f"\n合计候选 {total}，去重后入队 {len(fresh)}（已跳过历史 {len(seen)} 篇）")
    print("入队分布：", dict(dist))

    # ---- 覆盖度自检：窗口内每一天各有多少候选 ----
    per_day = collections.Counter(p.get("published", "?") for p in fresh)
    print("\n逐日覆盖度自检：")
    empty = []
    day = d0
    while day <= d1:
        k = day.isoformat()
        n = per_day.get(k, 0)
        print(f"  {k}  {'#' * min(n, 60)} {n}")
        if n == 0:
            empty.append(k)
        day += datetime.timedelta(days=1)
    undated = per_day.get("?", 0)
    if undated:
        print(f"  （无日期 {undated} 篇）")
    if empty:
        print(f"\n⚠ 有 {len(empty)} 天没有候选：{', '.join(empty)}")
        print("  arXiv 周末与节假日不公告，属于正常；若工作日也空，说明查询词覆盖不到，需要改 columns.json。")
    else:
        print("\n✓ 窗口内每一天都有候选覆盖")
    if capped:
        for name, n, cap in capped:
            print(f"⚠ {name} 候选 {n} 篇超过 --per-col={cap}，已按发布时间截断，"
                  f"想看全量请去掉 --per-col")
    print("→ data/queue.json 是下一步精读要处理的清单")


if __name__ == "__main__":
    argv = sys.argv[1:]
    per_col = 0
    if "--per-col" in argv:
        i = argv.index("--per-col")
        per_col = int(argv[i + 1])
        del argv[i:i + 2]
    repo = argv[0] if argv else "."
    days = int(argv[1]) if len(argv) > 1 else None
    main(repo, days, per_col)
