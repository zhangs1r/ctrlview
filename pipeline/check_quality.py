#!/usr/bin/env python3
"""精读质量自检：抓 AI 味残留 + 结构性问题，超阈值 exit 1。

与 qu-ai-wei 的关系：那是"怎么改"，这是"改完有没有改干净"的机器校验。
正则从 qu-ai-wei/pattern-catalog.md 的骨架条目提取。
"""
import re, sys

LIMIT = {
    "套话标题": 0,
    "预判标签": 0,
    "对称骨架": 0,
    "假揭示": 0,
    "推论台阶": 1,
    "长难句": 0,
    "代码块未闭合": 0,
}

PATTERNS = {
    "套话标题": r'(?m)^#{1,3}\s*(先说人话|一眼看懂|论文说了啥|一文读懂|十分钟读懂|'
                r'干货|解读一下|带你了解|深入浅出|通俗易懂|接下来)',
    "预判标签": r'值得注意|值得一提|显而易见|说实话|打个比方|要想象一下|'
                r'简单来说|说白了|核心逻辑很清晰|希望有帮助|不难看出',
    "对称骨架": r'不是.{1,15}而是|并非.{1,15}而是|不只.{1,15}也|不仅.{1,15}也|'
                r'与其.{1,12}不如|看似.{1,15}本质|既是.{1,10}也是',
    "假揭示": r'本质上|实际上|真正.{1,4}是|深层意义|这说明|这意味着|'
              r'体现了|提醒我们|揭示了',
    "推论台阶": r'这意味着|这说明|进一步|由此可见|从而得出',
}


def check(md):
    issues = []
    for name, pat in PATTERNS.items():
        hits = [(md[:m.start()].count("\n") + 1, m.group(0))
                for m in re.finditer(pat, md)]
        if len(hits) > LIMIT[name]:
            issues.append((name, len(hits), hits[:6]))

    # 长难句（跳过代码块、表格、**公式块** —— 公式长不是长难句）
    body = re.sub(r"```.*?```", "", md, flags=re.S)
    body = re.sub(r"(?m)^\|.*$", "", body)
    body = re.sub(r"\$\$.*?\$\$", "FORMULA", body, flags=re.S)
    body = re.sub(r"\$[^$\n]+\$", "f", body)
    longs = []
    for para in re.split(r"\n\s*\n", body):
        if para.lstrip().startswith(("#", ">", "-", "*", "|")):
            continue
        base = body[:body.find(para)].count("\n") + 1
        for sent in re.split(r"[。！？；]", para):
            s = re.sub(r"\s+", "", sent)
            if len(s) > 90:
                longs.append((base, len(s), s[:38] + "…"))
    if longs:
        issues.append(("长难句", len(longs), [(l, f"{c}字 {t}") for l, c, t in longs[:5]]))

    if md.count("```") % 2:
        issues.append(("代码块未闭合", 1, [(0, f"``` 出现 {md.count('```')} 次")]))
    return issues


if __name__ == "__main__":
    md = open(sys.argv[1], encoding="utf-8").read()
    iss = check(md)
    if not iss:
        print("✓ 自检通过，无 AI 味残留")
        sys.exit(0)
    print(f"✗ 发现 {len(iss)} 类问题：\n")
    for name, cnt, det in iss:
        print(f"  【{name}】{cnt} 处 (阈值 {LIMIT.get(name, '?')})")
        for ln, t in det:
            print(f"     L{ln}: {t}")
    sys.exit(1)
