"""Shared paths and helpers for the tech-daily-podcast pipeline."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPELINE = os.path.join(ROOT, "pipeline")
DATA_DIR = os.path.join(ROOT, "data")
EPISODES_DIR = os.path.join(ROOT, "episodes")
AUDIO_DIR = os.path.join(ROOT, "audio")
SEEN_FILE = os.path.join(DATA_DIR, "seen.json")
METADATA_FILE = os.path.join(DATA_DIR, "metadata.json")

TTS_VENV = os.path.expanduser("~/.hermes/tts/edge-tts")
EDGE_TTS = os.path.join(TTS_VENV, "bin", "edge-tts")
FFMPEG = os.path.expanduser("~/.hermes/tools/ffmpeg-9.0.1-darwin-arm64/ffmpeg")
if not os.path.exists(FFMPEG):  # fallback: system
    FFMPEG = "ffmpeg"

# 双主播声音: 男 = 云扬 (新闻腔, 专业稳重), 女 = 晓晓 (温暖清晰)
VOICES = {
    "M": "zh-CN-YunyangNeural",
    "F": "zh-CN-XiaoxiaoNeural",
}

def today_str() -> str:
    import datetime
    return datetime.date.today().isoformat()

def episode_dir(date_str: str) -> str:
    return os.path.join(EPISODES_DIR, date_str)
