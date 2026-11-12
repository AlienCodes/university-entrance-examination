"""考研音频自检（由专八 qa_audio.py 复制）：复用高考 tools/tts/qa.py（语音识别回转比对 + UTMOS 自然度 + 响度独立测量），输出到 考研/audio/qa_report.*。
用法：/opt/ttsenv/bin/python 六级作文/tools/qa_audio.py k01 k02 …（不写则检查全部）
考研补充：识别比对用的参考文本把 2010s 读作 twenty tens（高考共用的 textnorm.decade 没有这一条，k13、k26 自检报错；朗读用的 make_audio 已有同样的读法），
只在这里替换函数，高考程序不改。
"""
import sys
from pathlib import Path
from types import SimpleNamespace

C4 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(C4.parent / 'tools' / 'tts'))
import textnorm  # noqa: E402
import qa  # noqa: E402

_decade = textnorm.decade


def decade(n):
    if 2000 <= n < 2100 and n % 100 in (0, 10):
        return 'twenty tens' if n % 100 == 10 else 'two thousands'
    return _decade(n)


textnorm.decade = decade
qa.OUT = C4 / 'audio'
qa.run(SimpleNamespace(voices=['cet4_male'], only=sys.argv[1:] or None))
