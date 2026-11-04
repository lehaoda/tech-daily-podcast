#!/usr/bin/env python3
"""抓取正规媒体 RSS 的科技/AI 新闻 → 去重(含历史已播) → 打分 → 输出候选 news.json

用法: python3 pipeline/fetch_news.py
输出: episodes/<今天>/news.json   (含最多 25 条候选, 每条带来源/链接/摘要)
规则:
  - 只收录近 24h(不足时自动放宽到 48h/72h) 的新闻
  - data/seen.json 中已出现的文章不再出现(保证不重复播过)
  - 本次进入候选池的文章会立即写入 seen —— 就算今天失败,明天也不会重播
"""
import concurrent.futures
import hashlib
import html
import json
import os
import re
import ssl
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from common import DATA_DIR, SEEN_FILE, episode_dir, today_str

# (显示名, URL, 权重, 类型)。全是正规媒体/官方渠道; 权重代表该来源的优先度
# 注: 36氪 / 机器之心 官方 RSS 有反爬墙(返回 JS/HTML), 已移除; 中文源由量子位/IT之家/爱范儿覆盖
FEEDS = [
    ("OpenAI Blog", "https://openai.com/news/rss.xml", 4.0, "rss"),
    ("量子位", "https://www.qbitai.com/feed", 3.5, "rss"),
    ("Hugging Face Blog", "https://huggingface.co/blog/feed.xml", 3.5, "rss"),
    ("TechCrunch", "https://techcrunch.com/feed/", 3.0, "rss"),
    ("MIT Technology Review", "https://www.technologyreview.com/feed/", 3.0, "rss"),
    ("The Verge", "https://www.theverge.com/rss/index.xml", 2.5, "atom"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", 2.5, "rss"),
    ("IT之家", "https://www.ithome.com/rss/", 2.5, "rss"),
    ("爱范儿", "https://www.ifanr.com/feed", 2.0, "rss"),
    ("Hacker News (frontpage)", "https://hnrss.org/frontpage", 1.5, "rss"),
]

STRONG_KW = re.compile(
    r"(大模型|LLM|GPT|Gemini|Claude|DeepSeek|OpenAI|Anthropic|AI|人工智能|AIGC|"
    r"神经网络|机器人|具身智能|智能体|agent|模型|推理芯片|GPU|NPU|AI芯片|"
    r"Grok|Llama|Mistral|扩散模型|多模态|AGI|算力|大语言模型)",
    re.IGNORECASE,
)
TECH_KW = re.compile(
    r"(芯片|半导体|晶圆|英伟达|NVIDIA|高通|苹果|Apple|华为|Google|谷歌|Microsoft|"
    r"微软|Meta|亚马逊|Amazon|特斯拉|Tesla|三星|台积电|AMD|Intel|英特尔|小米|字节|"
    r"百度|阿里|腾讯|发布|推出|融资|估值|IPO|上市|监管|反洗钱|法规|法案|量子|卫星|"
    r"电动车|自动驾驶|AR|VR|头显|芯片厂|数据中心|云|服务器|手机|笔记本|电脑|平板)",
    re.IGNORECASE,
)


def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_date(text, kind):
    if not text:
        return None
    text = text.strip()
    try:
        if kind == "atom":
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsedate_to_datetime(text)
    except Exception:
        return None


ATOM = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/elements/1.1/}"


def _strip_block(s):
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s or "", flags=re.S)
    return s


def regex_items(raw):
    """XML 解析失败时的兜底: 正则抽 <item>/<entry> 块"""
    text = raw.decode("utf-8", "ignore")
    items = []
    blocks = re.findall(r"<item[\s>].*?</item>", text, re.S)
    entry_mode = False
    if not blocks:
        blocks = re.findall(r"<entry[\s>].*?</entry>", text, re.S)
        entry_mode = True
    for block in blocks:
        def g(tag):
            m = re.search(r"<%s[^>]*>(.*?)</%s>" % (tag, tag), block, re.S)
            return _strip_block(m.group(1)).strip() if m else ""

        title = strip_html(g("title"))
        link = g("link").strip()
        if not link:
            m = re.search(r'<link[^>]*href=["\']([^"\']+)', block)
            link = m.group(1) if m else ""
        pub_s = g("pubDate") or g("published") or g("updated")
        desc = strip_html(g("description") or g("summary") or g("content"))
        pub = parse_date(pub_s, "atom" if entry_mode else "rss")
        if title and link:
            items.append({"title": title, "link": link, "published": pub, "desc": desc[:300]})
    return items


def fetch_feed(name, url, weight, kind):
    ua = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    req = urllib.request.Request(url, headers=ua)
    with urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context()) as r:
        raw = r.read()
    items = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        items = regex_items(raw)
        if items:
            return name, items, None
        # 重试: 修复 & 后仍失败则放弃
        try:
            raw2 = re.sub(rb"&(?!#\d+;|#\w+;|[a-zA-Z]\w*;)", b"&amp;", raw)
            root = ET.fromstring(raw2)
        except ET.ParseError as e:
            return name, [], f"xml error: {e}"
    if kind == "atom":
        entries = root.findall(f"{ATOM}entry") or root.iter(f"{ATOM}entry")
        for en in entries:
            link = ""
            for a in en.iter(f"{ATOM}link"):
                if a.get("rel") in (None, "alternate"):
                    link = a.get("href", "")
                    break
            title = strip_html((en.findtext(f"{ATOM}title") or ""))
            pub = parse_date(en.findtext(f"{ATOM}published") or en.findtext(f"{ATOM}updated"), "atom")
            desc = strip_html(en.findtext(f"{ATOM}summary") or en.findtext(f"{ATOM}content"))
            if title and link:
                items.append({"title": title, "link": link, "published": pub, "desc": desc[:300]})
    else:
        for it in root.iter("item"):
            title = strip_html(it.findtext("title") or "")
            link = (it.findtext("link") or "").strip()
            pub = parse_date(it.findtext("pubDate") or it.findtext(f"{DC}date"), "rss")
            desc = strip_html(it.findtext("description") or it.findtext("summary") or "")
            if title and link:
                items.append({"title": title, "link": link, "published": pub, "desc": desc[:300]})
    return name, items, None


def norm_title(t: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", t.lower())


def score_item(it):
    text = it["title"] + " " + it.get("desc", "")
    s = it["source_weight"]
    if STRONG_KW.search(text):
        s += 2.0
    if TECH_KW.search(text):
        s += 1.0
    age_h = it.get("age_hours", 72)
    if age_h <= 6:
        s += 1.0
    elif age_h <= 24:
        s += 0.5
    return round(s, 2)


def load_seen():
    try:
        with open(SEEN_FILE) as f:
            return json.load(f)
    except Exception:
        return {"items": {}, "updated": None}


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    now = datetime.now(timezone.utc)
    seen = load_seen()
    seen_set = set(seen["items"].keys())  # keys = sha1(normalized url + title)

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(fetch_feed, *spec) for spec in FEEDS]
        for f in concurrent.futures.as_completed(futs):
            results.append(f.result())

    print("feed fetch results:", file=sys.stderr)
    pool = []
    failed = []
    for name, items, err in results:
        if err:
            failed.append(f"{name}: {err}")
            continue
        print(f"  {name}: {len(items)} raw items", file=sys.stderr)
        for it in items:
            it["source"] = name
            it["source_weight"] = next(w for n2, u2, w, k2 in FEEDS if n2 == name)
            key = hashlib.sha1((it["link"] + "|" + it["title"]).encode()).hexdigest()
            it["key"] = key
            pool.append(it)

    # 历史去重: 已播过的(或已进过候选池的)不再出现
    fresh = [it for it in pool if it["key"] not in seen_set]
    # 按发布时间过滤 + 打分; 时间窗 24h → 48h → 72h 逐级放宽
    window = None
    for hours in (24, 48, 72):
        cands = []
        for it in fresh:
            if it["published"] is None:
                continue
            age = now - it["published"].astimezone(timezone.utc)
            hours_age = age.total_seconds() / 3600
            if 0 <= hours_age <= hours:
                it["age_hours"] = round(hours_age, 1)
                it["score"] = score_item(it)
                cands.append(it)
        if len(cands) >= 6 or hours == 72:
            window = hours
            break
    cands.sort(key=lambda x: (-x["score"], x["age_hours"]))

    # 跨源同题去重(同一事件多个来源): 保留分数最高者,其余仍标记 seen
    by_title = {}
    for it in cands:
        nt = norm_title(it["title"])
        if nt in by_title:
            if it["score"] > by_title[nt]["score"]:
                keep, drop = it, by_title[nt]
                by_title[nt] = keep
            else:
                drop = it
        else:
            by_title[nt] = it
    kept = list(by_title.values())
    kept.sort(key=lambda x: (-x["score"], x["age_hours"]))
    top = kept[:25]

    # 把本次候选池全部写入 seen(防止明天重复)
    for it in kept:
        seen["items"][it["key"]] = {
            "title": it["title"], "source": it["source"],
            "published": it["published"].astimezone(timezone.utc).isoformat() if it["published"] else None,
            "first_seen": now.isoformat(),
        }
    # 清理 90 天前的记录
    cutoff = now - timedelta(days=90)
    seen["items"] = {
        k: v for k, v in seen["items"].items()
        if v.get("first_seen") and datetime.fromisoformat(v["first_seen"]) >= cutoff
    }
    seen["updated"] = now.isoformat()
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f, ensure_ascii=False, indent=1)

    out_dir = episode_dir(today_str())
    os.makedirs(out_dir, exist_ok=True)
    payload = {
        "date": today_str(),
        "window_hours": window,
        "fetched_at": now.isoformat(),
        "failed_feeds": failed,
        "candidates": [
            {
                "title": it["title"], "source": it["source"], "link": it["link"],
                "published": it["published"].astimezone(timezone.utc).isoformat(),
                "age_hours": it["age_hours"], "score": it["score"], "summary": it.get("desc", ""),
            }
            for it in top
        ],
    }
    out_file = os.path.join(out_dir, "news.json")
    with open(out_file, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    print(f"\nOK  {len(top)} candidates → {out_file} (window {window}h, seen total {len(seen['items'])})")
    for i, it in enumerate(top, 1):
        print(f"  {i:2d}. [{it['score']:4.1f}] {it['title'][:70]}  — {it['source']} ({it['age_hours']}h)")
    if len(top) < 4:
        print("WARN: 候选不足 4 条, 今天可能无法凑齐内容", file=sys.stderr)
    if failed:
        print("FAIL(已忽略): " + "; ".join(failed[:4]), file=sys.stderr)


if __name__ == "__main__":
    main()
