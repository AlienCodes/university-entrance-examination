"""每篇配音做完立刻做的语音识别分诊（及时做、及时查，铁律 15）：

    /opt/ttsenv/bin/python tools/tts/识别分诊.py 专八 t25 [t26 …] [--rev <提交>]

自检报告（qa_report.json）里这一篇的识别差异，程序先放过确定无害的（英美拼写、连字符 / 空格、撇号引号、数字写法、句中大写的专名——专名读音另由
pron_check 人工核对登记）；其余的自动做“整句前后多留 0.5 秒 + 按音频分句截取”重新识别，任何一种截取听出了原词就放过（识别器按上下文猜错）；
三种都听不出、也没登记在 <项目>/audio/识别差异已核.json（人工确认无害的差异）里的列为“待核”，退出码 1——批量配音（batch_audio.sh）就停在这一篇，当场改读音、试合成（识别复核.py 试合成）、重做这一篇再接着做。
--rev：读那次提交里的音频和报告（双向验证用：专八 t25 改读音之前的提交里 toiled 必须报出来）。"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parent.parent
args = sys.argv[1:]
rev = None
if '--rev' in args:
    i = args.index('--rev')
    rev = args[i + 1]
    args = args[:i] + args[i + 2:]
proj, ids = args[0], args[1:]


def read(path, binary=False):
    if rev:
        out = subprocess.run(['git', '-C', str(R), 'show', f'{rev}:{path}'], capture_output=True, check=True).stdout
        return out if binary else out.decode('utf-8')
    p = R / path
    return p.read_bytes() if binary else p.read_text('utf-8')


VAR = [('ise', 'ize'), ('isation', 'ization'), ('our', 'or'), ('lled', 'led'), ('lling', 'ling'), ('tre', 'ter'), ('bre', 'ber'), ('ce', 'se'),
       ('grey', 'gray'), ('ogue', 'og'), ('yse', 'yze'), ('mme', 'm'), ('ae', 'e')]
NUM = re.compile(r'^(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|'
                 r'eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|and|point|'
                 r'dollars?|pounds?|euros?|percent|first|second|third|[a-z]+th)(?: |$)')


NAMES = set()


def benign(a, b, text):
    A, B = re.sub(r"[’'\"“”‘]", '', a), re.sub(r"[’'\"“”‘]", '', b)
    if A == B or A.replace(' ', '').replace('-', '') == B.replace(' ', '').replace('-', ''):
        return True
    if any((x in A or x in B) and A.replace(x, y) == B.replace(x, y) for x, y in VAR):
        return True
    if (NUM.match(A) or not A) and (re.search(r'\d', B) or not B or B in ('point', 'and')):   # 识别器把数字写成阿拉伯数字（含小数点、and）
        return True
    if A and all(re.sub(r"['’]s$", '', w) in NAMES for w in a.split()):
        return True                                                       # 已人工核对过读音的专名（pron_check 的 专名读音已核.json）：识别器按上下文猜拼写
    if A and all(re.search(rf'(?<![.!?“"‘(]\s)(?<!^)\b{re.escape(w)}\b', text, re.I) and
                 re.search(rf'\b{re.escape(w[0].upper() + w[1:])}', text) for w in A.split()):
        return True                                                       # 句中大写的专名（读音另由 pron_check 核对）
    return False


def main():
    import numpy as np
    sys.path.insert(0, str(HERE))
    import glob
    import sherpa_onnx
    d = Path(glob.glob(str(HERE / 'models' / 'sherpa-onnx-nemo-parakeet*'))[0])
    asr = sherpa_onnx.OfflineRecognizer.from_transducer(encoder=str(d / 'encoder.int8.onnx'), decoder=str(d / 'decoder.int8.onnx'),
                                                        joiner=str(d / 'joiner.int8.onnx'), tokens=str(d / 'tokens.txt'),
                                                        model_type='nemo_transducer', num_threads=4)

    def rec(a):
        s = asr.create_stream()
        s.accept_waveform(16000, a)
        asr.decode_stream(s)
        return s.result.text.lower()

    pf = R / proj / 'tools' / '专名读音已核.json'
    if pf.exists():
        NAMES.update(w.lower() for w in json.loads(pf.read_text('utf-8')) if w[:1].isupper())
        NAMES.update(re.sub(r"['’]s$", '', w.lower()) for w in json.loads(pf.read_text('utf-8')) if w[:1].isupper())
    reg_f = R / proj / 'audio' / '识别差异已核.json'                  # 人工确认无害、不用改的差异（句子编号 → {朗读文本里的词: 理由}），以后不再报
    reg = json.loads(reg_f.read_text('utf-8')) if reg_f.exists() else {}
    rep = json.loads(read(f'{proj}/audio/qa_report.json'))['cet4_male']
    T = json.loads(read(f'{proj}/audio/timings.json'))['cet4_male']
    todo = []
    for pid in ids:
        tm = T[pid]
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', '-', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'],
                             input=read(f'{proj}/audio/{tm["file"]}', True), capture_output=True).stdout
        a = np.frombuffer(raw, np.float32)
        cut = lambda x, y: a[max(0, int(x * 16000)):int(y * 16000)]
        n = 0
        for s in rep[pid]['sentences']:
            it = tm['sentences'][s['k'] - 1]
            ops = [o for o in s['ops'] if not benign(o[0], o[1], it['text']) and o[0] not in reg.get(f'{pid}:{s["k"]}', {})]
            if not ops:
                continue
            heard = [rec(cut(it['start'] - 0.5, it['end'] + 0.5))] + [rec(cut(x - 0.3, y + 0.3)) for x, y in it['parts']]
            norm = lambda t: re.sub(r"[^a-z0-9' ]", ' ', t.replace('’', "'"))
            left = [o for o in ops if not (o[0] and any(re.search(rf"\b{re.escape(o[0])}\b", norm(h)) for h in heard))]
            n += len(ops)
            if left:
                todo.append(f'{pid}:{s["k"]} {left}  朗读：{it["read"][:120]}  | 整句重听：{heard[0][:120]}')
        print(f'{pid}：识别差异要复核 {n} 处，自动截取复核后待核 {sum(1 for x in todo if x.startswith(pid + ":"))} 处', flush=True)
    for x in todo:
        print('  待核', x, flush=True)
    sys.exit(1 if todo else 0)


if __name__ == '__main__':
    main()
