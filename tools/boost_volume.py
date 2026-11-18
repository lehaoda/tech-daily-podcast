#!/usr/bin/env python3
"""硬盘存量音频整体 +20% 音量(2026-11-18 用户要求), 八卦局视频轨同步替换。
原文件已备份: /Volumes/DataVault/podcast/backup_pre_gain_2026-11-18.tar.gz
"""
import glob
import os
import re
import subprocess
import sys

FF = os.path.expanduser("~/.hermes/tools/ffmpeg-9.0.1-darwin-arm64/ffmpeg")
AF = "volume=1.2,alimiter=limit=0.95:level=false"
ROOT = "/Volumes/DataVault/podcast"


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"fail: {cmd[:2]} ... {r.stderr[-300:]}")
    return r


def boost_audio(src, codec_args, out):
    tmp = out + ".new" + os.path.splitext(out)[1]
    run([FF, "-y", "-i", src, "-af", AF] + codec_args + ["-ar", "24000", "-ac", "1", tmp])
    os.replace(tmp, out)


def detect(path):
    r = run([FF, "-i", path])
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB.*?max_volume:\s*(-?[\d.]+) dB", r.stderr, re.S)
    return m.groups() if m else None


def main():
    jobs = []
    for d in ("episodes", "tech_gossip/episodes"):
        base = os.path.join(ROOT, d)
        for f in sorted(glob.glob(os.path.join(base, "*"))):
            name = os.path.basename(f)
            if re.match(r"^\d{4}-\d{2}-\d{2}\.m4a$", name):
                jobs.append((f, ["-c:a", "aac", "-b:a", "64k"]))
            elif re.match(r"^\d{4}-\d{2}-\d{2}\.mp3$", name):
                jobs.append((f, ["-c:a", "libmp3lame", "-b:a", "64k"]))
    for f, args in jobs:
        boost_audio(f, args, f)
        print("BOOST", os.path.relpath(f, ROOT), os.path.getsize(f) // 1024, "KB", flush=True)

    # 八卦局视频: 视频流拷贝 + 音频换成已增益的同日期 m4a
    vdir = os.path.join(ROOT, "tech_gossip/videos")
    edir = os.path.join(ROOT, "tech_gossip/episodes")
    for f in sorted(glob.glob(os.path.join(vdir, "*.mp4"))):
        date = os.path.basename(f)[:-4]
        m4a = os.path.join(edir, f"{date}.m4a")
        if not os.path.exists(m4a):
            print("SKIP video (no m4a):", f, flush=True)
            continue
        tmp = f + ".new.mp4"
        run([FF, "-y", "-i", f, "-i", m4a, "-map", "0:v", "-map", "1:a",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "64k", "-shortest", tmp])
        os.replace(tmp, f)
        print("VIDEO", os.path.relpath(f, ROOT), os.path.getsize(f) // 1024, "KB", flush=True)

    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
