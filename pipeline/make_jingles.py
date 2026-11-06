#!/usr/bin/env python3
"""生成「乐见未来」开场/结束 jingle(本地合成,零版权依赖,可复现)。

用法: .venv/bin/python pipeline/make_jingles.py --style both --outdir <dir>
输出: jingle_in_A.wav / jingle_out_A.wav / jingle_in_B.wav / jingle_out_B.wav (44.1kHz stereo)

风格:
  A = morning-tech: 明亮拨弦上行琶音 + pad + 轻鼓点,清晨科技感
  B = minimal-piano: Karplus-Strong 钢琴感,温柔极简

jingle 是素材文件:定稿后复制到 assets/jingle_in.wav + assets/jingle_out.wav,
发布流水线在 tts 拼接时把 in 放最前、out 放最后。
"""
import argparse
import os
import wave

import numpy as np

SR = 44100


def note_freq(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def pluck(freq, dur, harmonics=(1.0, 0.4, 0.18, 0.07), decay=3.5):
    """指数衰减的加性合成拨弦音。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for i, amp in enumerate(harmonics, start=1):
        out += amp * np.sin(2 * np.pi * freq * i * t)
    out *= np.exp(-decay * t)
    out[: int(0.003 * SR)] *= np.linspace(0, 1, int(0.003 * SR))
    return out


def pad(frequencies, dur, attack=0.4, release=1.2, level=1.0):
    """柔 pad: 多重正弦 + 轻微失谐 + 渐变包络。"""
    total = int((dur + release) * SR)
    t = np.arange(total) / SR
    out = np.zeros(total)
    for f in frequencies:
        for detune, amp in ((1.0, 1.0), (1.003, 0.35), (0.997, 0.35)):
            out += amp * np.sin(2 * np.pi * f * detune * t)
            out += 0.4 * np.sin(2 * np.pi * f * 2 * detune * t)
    env = np.ones(total)
    na = int(attack * SR)
    nr = int(release * SR)
    env[:na] = np.linspace(0, 1, na) ** 2
    env[-nr:] = np.linspace(1, 0, nr) ** 2
    out *= env
    return out / max(np.max(np.abs(out)), 1e-9) * level


def karplus_strong(freq, dur, damping=0.996):
    """Karplus-Strong 弦振荡 → 钢琴/吉他质感。"""
    period = max(2, int(SR / freq))
    n = int(dur * SR)
    buf = np.random.default_rng(int(freq * 7)).uniform(-1, 1, period)
    out = np.zeros(n)
    for i in range(n):
        cur = buf[i % period]
        nxt = 0.5 * (cur + buf[(i + 1) % period]) * damping
        buf[i % period] = nxt
        out[i] = cur
    out *= np.exp(-2.2 * np.arange(n) / SR)
    return out


def kick(dur=0.18):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 110 * np.exp(-30 * t) + 42
    phase = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(phase) * np.exp(-t * 28)


def shimmer(dur=0.8, seed=7):
    """开头 riser: 带通噪声上扫(简化卷积版)。"""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    noise = rng.uniform(-1, 1, n)
    out = np.zeros(n)
    win = 600
    for i in range(0, n - win, 8):
        band = int(win * (1 - 0.8 * i / n) + 24)
        seg = noise[i:i + win]
        sm = np.convolve(seg, np.ones(band) / band, mode="full")[:win]
        out[i:i + win] += sm
    return out * (np.linspace(0, 1, n) ** 1.6) * 0.5


def stereo(mono, delay_ms=6.0):
    """mono → stereo: 右声道 6ms comb + 低通混入,空气感。"""
    d = int(delay_ms / 1000 * SR)
    lp = np.convolve(mono, np.ones(3) / 3, mode="same")
    right = np.zeros_like(mono)
    right[:-d] = mono[d:] * 0.85 + lp[d:] * 0.15
    right[-d:] = mono[-d:]
    return np.stack([mono, right], axis=1)


def render(parts, total, outpath):
    """parts: [(start_s, mono_wave)] → stereo wav, peak 0.82, 首尾淡入淡出。"""
    mono = np.zeros(int(total * SR))
    for start, wave_ in parts:
        i0 = int(start * SR)
        i1 = min(i0 + len(wave_), len(mono))
        mono[i0:i1] += wave_[: i1 - i0]
    peak = np.max(np.abs(mono))
    if peak > 0:
        mono = mono / peak * 0.82
    st = stereo(mono)
    fr = int(0.18 * SR)
    st[:fr] *= np.linspace(0, 1, fr)[:, None]
    ft = int(0.22 * SR)
    st[-ft:] *= np.linspace(1, 0, ft)[:, None]
    out = np.clip(st, -1, 1)
    pcm = (out * 32767).astype("<i2")
    with wave.open(outpath, "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(pcm.tobytes())
    return outpath


def style_a_in():
    """A in: 116BPM,riser + Cmaj9 pad + 上行琶音 ×2 + 轻鼓,尾音 chord。"""
    beat = 60.0 / 116
    parts = []
    parts.append((0.0, shimmer(0.9, seed=11)))
    parts.append((0.35, pad([note_freq(m) for m in (48, 52, 55, 50)], 3.2, 0.5, 1.6, 0.30)))
    seq = [72, 76, 79, 84, 88, 79, 84, 88]
    for i, m in enumerate(seq):
        parts.append((0.9 + i * beat / 2, pluck(note_freq(m), 0.45, decay=4.5)))
    for i, m in enumerate((84, 88, 91, 96)):
        parts.append((0.9 + (8 + i) * beat / 2 + 0.002,
                      pluck(note_freq(m), 0.5, decay=5.0, harmonics=(1, 0.5, 0.22, 0.1))))
    for b in (0, 4, 7):
        parts.append((0.9 + b * beat, kick() * 0.5))
    parts.append((0.9 + 7 * beat, kick(0.22) * 0.7))
    for m in (84, 88, 91):
        parts.append((0.9 + 12 * beat, pluck(note_freq(m), 1.4, decay=2.2)))
    return parts, 0.9 + 12 * beat + 1.7


def style_a_out():
    """A out: 下行琶音 + 落地 Cmaj 长和弦。"""
    beat = 60.0 / 116
    parts = []
    parts.append((0.0, pad([note_freq(m) for m in (48, 52, 55, 59)], 3.6, 0.3, 2.4, 0.28)))
    for i, m in enumerate((88, 84, 79, 76, 72, 67, 64, 60)):
        parts.append((i * beat / 2, pluck(note_freq(m), 0.42, decay=4.0)))
    for m, lv in ((48, 0.5), (55, 0.4), (60, 0.4), (64, 0.35)):
        parts.append((4 * beat, pluck(note_freq(m), 2.6, decay=1.6) * lv))
    return parts, 4 * beat + 3.0


def style_b_in():
    """B in: 92BPM,暖 pad + 四音钢琴动机上行,尾和弦。"""
    beat = 60.0 / 92
    parts = []
    parts.append((0.0, pad([note_freq(m) for m in (41, 45, 48)], 4.0, 1.2, 2.0, 0.22)))
    for i, m in enumerate((64, 67, 72, 76, 72, 76, 79, 84)):
        parts.append((0.8 + i * beat, karplus_strong(note_freq(m), 0.9) * (0.5 if i < 4 else 0.55)))
    for m in (60, 64, 67):
        parts.append((0.8 + 8 * beat, karplus_strong(note_freq(m), 2.2) * 0.4))
    return parts, 0.8 + 8 * beat + 2.5


def style_b_out():
    """B out: 钢琴下行 + 长尾和弦。"""
    beat = 60.0 / 92
    parts = []
    parts.append((0.0, pad([note_freq(m) for m in (41, 45, 48)], 4.2, 0.4, 3.0, 0.20)))
    for i, m in enumerate((76, 72, 67, 64, 60, 55, 52, 48)):
        parts.append((i * beat, karplus_strong(note_freq(m), 0.8) * (0.45 if i < 4 else 0.4)))
    for m in (48, 52, 55):
        parts.append((4 * beat, karplus_strong(note_freq(m), 2.8) * 0.42))
    return parts, 4 * beat + 3.2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", default="both", choices=["A", "B", "both"])
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    jobs = {
        "A": [("jingle_in_A.wav", style_a_in), ("jingle_out_A.wav", style_a_out)],
        "B": [("jingle_in_B.wav", style_b_in), ("jingle_out_B.wav", style_b_out)],
    }
    for s in ("A", "B") if args.style == "both" else (args.style,):
        for name, fn in jobs[s]:
            parts, total = fn()
            final = os.path.join(args.outdir, name)
            render(parts, total, final)
            print(f"{final}  {total:.1f}s")


if __name__ == "__main__":
    main()
