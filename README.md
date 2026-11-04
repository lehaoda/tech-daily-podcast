# 科技早报 · 播客

每天 5 分钟,男女双主播(云扬 × 晓晓)对谈科技与 AI 新闻。新闻全部来自正规媒体 RSS,
自动去重(播过的不会重复),每集描述附原始链接。

- 频道页: https://lehaoda.github.io/tech-daily-podcast/
- RSS: https://lehaoda.github.io/tech-daily-podcast/feed.xml
- 音频: https://lehaoda.github.io/tech-daily-podcast/audio/<日期>.mp3

## 工作流(每天 7:00 由 Hermes cron 自动执行)

1. `pipeline/fetch_news.py` — 并发抓取 10 家正规媒体 RSS(OpenAI、量子位、HF、TechCrunch、
   The Verge、MIT Tech Review、Ars Technica、IT之家、爱范儿、Hacker News),
   过滤 24h 内(不足自动放宽到 48/72h),按关键词打分,
   与 `data/seen.json` 历史库比对去重 → `episodes/<日期>/news.json`(25 条候选)。
   候选进池即写入 seen,保证失败重试也不会重复播。
2. Agent 从候选中精选 6-8 条,写双主播对谈稿 `episodes/<日期>/script.txt`
   (`M：`/`F：` 行格式,1150-1350 字 ≈ 5 分钟)+ `summary.md`(每条新闻的来源链接)。
   只用候选池内的事实,不虚构。
3. `pipeline/tts_episode.py` — edge-tts 逐句合成(男 `zh-CN-YunyangNeural` /
   女 `zh-CN-XiaoxiaoNeural`),ffmpeg 拼接 + 句间停顿 → `episodes/<日期>/episode.mp3`。
4. `pipeline/publish.py` — 重建 `feed.xml`(保留最近 20 期) + `index.html`,
   推 GitHub Pages,轮询验证线上 feed 与音频可访问。

手动重跑某天: `python3 pipeline/fetch_news.py` → 写稿 →
`python3 pipeline/tts_episode.py episodes/<日期>/script.txt` →
`python3 pipeline/publish.py episodes/<日期>`

## 目录

```
feed.xml            播客 RSS(自动生成)
index.html          频道页(自动生成, 含播放器)
cover.png           3000x3000 封面
audio/              各集 MP3
episodes/<日期>/    news.json / script.txt / summary.md / episode.mp3
pipeline/           流水线脚本
data/               metadata.json(频道元数据) / seen.json(去重历史) / episodes.json
.venv/              make_cover.py 用的 Pillow(仅封面生成一次需要)
```

## 入驻播客平台

RSS 已托管在 GitHub Pages(公开、稳定、免费)。在各平台"提交节目"填入
`https://lehaoda.github.io/tech-daily-podcast/feed.xml`:
- Apple Podcasts: https://podcasts.apple.com 创作者提交,或 https://apps.apple.com/podcasts/new
- Spotify for Creators: https://artists.spotify.com (Podcasts → 提交 feed)
- 小宇宙: https://www.xiaoyuzhoufm.com 创作者后台提交
- YouTube Music / Amazon Music / Overcast 同理

需要新 Apple ID 注册时走 Apple Podcasts Connect;通常几天内过审。
