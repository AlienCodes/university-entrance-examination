"""双向验证：讲解配音的语速与音高起伏（踩坑 94；用户 2026-11-03：“语速太慢”“语气像哄小学生”）。
要识别模型（SenseVoice）与 librosa，只在本机跑（needs tts）。
  ① 有问题的版本：第 2 版第 56 题样片（仓库 audio/ 里的 mp3，标记停顿 0.55 秒、参考语速偏慢）→ 必须报“语速太慢”；
  ② 好的版本：用户本人讲课录音的一段（样本 语速_用户录音.flac，40 秒）→ 0 处；
  ③ 入口：候选汇总.py 调 语速语调.check_file；目标文件 tts/音色/用户本人_语速.json 存在且来自录音。
    /opt/ttsenv/bin/python tools/防复发/验证/语速语调.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / '高考语法填空/tools'), str(ROOT / 'tools/tts')]
import 挑参考 as PR  # noqa: E402
import 语速语调 as SY  # noqa: E402

bad = []
asr = PR.ASR()
old = ROOT / '高考语法填空/audio/2026 新课标Ⅰ卷 语法填空 第56题样片（用户本人声音）.mp3'
m, e = SY.check_file(old, asr)
hit = any('语速太慢' in x for x in e)
print(f"① 第 2 版样片：语速 {m['rate']:.2f}，{'报出“太慢”' if hit else '漏查'}（{e}）")
if not hit:
    bad.append('① 第 2 版样片没报“语速太慢”')
m, e = SY.check_file(Path(__file__).parent / '样本/语速_用户录音.flac', asr)
print(f"② 用户录音一段：语速 {m['rate']:.2f}，音高起伏 {m['f0sd_median']}，{len(e)} 处 {e}")
if e:
    bad.append('② 用户本人录音被判不合格')
t = json.loads(SY.TARGET.read_text('utf-8'))
if t.get('source') != '05.wav' or not t.get('rate'):
    bad.append('③ 目标文件不是从录音量的')
if 'SY.check_file' not in (ROOT / '高考语法填空/tools/候选汇总.py').read_text('utf-8'):
    bad.append('③ 候选汇总.py 没调 语速语调.check_file')
print('语速语调双向验证', '通过' if not bad else '失败：' + '；'.join(bad))
sys.exit(1 if bad else 0)
