"""本机预演用的假 qwen_tts（铁律 15：推送触发 Actions 之前，先按工作流的命令在本机把 qwen_synth.py 整条跑一遍）。
不下载模型：每次合成返回 预演_qwen/样本/ 里一段真实的 Qwen3-TTS 合成音频（按调用次数轮换），处理链、合格证照真的走。
用法见 预演.sh（放在 tools/防复发/：它是推送前的防复发预演，不是成品入口）。"""
import itertools
from pathlib import Path

import soundfile as sf

_S = sorted((Path(__file__).parent / '样本').glob('*.wav'))
_it = itertools.cycle(_S)


class Qwen3TTSModel:
    @classmethod
    def from_pretrained(cls, *a, **k):
        assert _S, '预演_qwen/样本/ 里没有 wav'
        return cls()

    def get_supported_speakers(self):
        return ['预演']

    def get_supported_languages(self):
        return ['chinese', 'english']

    def _one(self, max_new_tokens=None):
        x, sr = sf.read(str(next(_it)), dtype='float32')
        if max_new_tokens:                # 真模型在上限内自然停：轮到的样本比上限的 80% 长，就换一段放得下的完整样本（都放不下才截断）
            lim = max_new_tokens * 0.8 / 12.5
            if len(x) / sr > lim:
                fits = [p for p in _S if sf.info(str(p)).duration <= lim]
                if fits:
                    x, sr = sf.read(str(max(fits, key=lambda p: sf.info(str(p)).duration)), dtype='float32')
                else:
                    n = int(lim * sr)
                    x = x[:n].copy()
                    f = int(0.03 * sr)
                    x[-f:] *= __import__('numpy').linspace(1, 0, f, dtype='float32')
        return [x], sr

    def generate_custom_voice(self, **k):
        return self._one(k.get('max_new_tokens'))

    def generate_voice_clone(self, **k):
        return self._one(k.get('max_new_tokens'))

    def generate_voice_design(self, **k):
        return self._one()

    def create_voice_clone_prompt(self, **k):
        return [object()]
