"""专八音频自检（由六级 qa_audio.py 复制）。四级原说明：四级音频自检：复用高考 tools/tts/qa.py（语音识别回转比对 + UTMOS 自然度 + 响度独立测量），输出到 四级/audio/qa_report.*。
用法：python 四级/tools/qa_audio.py c60 c59 …（不写则检查全部）
"""
import sys
from pathlib import Path
from types import SimpleNamespace

C4 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(C4.parent / 'tools' / 'tts'))
import qa  # noqa: E402

qa.OUT = C4 / 'audio'
qa.run(SimpleNamespace(voices=['cet4_male'], only=sys.argv[1:] or None))
