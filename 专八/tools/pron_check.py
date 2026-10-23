"""专八专名读音登记检查（由中考 pron_check.py 复制，只换项目；CLAUDE.md 踩坑 40）：语音识别会按上下文“猜”专名的拼写，读错的专名会被放过（Ting-Hsuan 的 H 读成 aitch、Ms 读成 em-es，
女声那一轮都没查出来）。所以词典里查不到的词、加了读音修正的词，连同最终音标逐个人工核对后登记在 专名读音已核.json；
之后出现没登记的词或音标变了，就报错，必须人工核对音标（必要时试合成 + 语音识别）后再登记。

    /opt/ttsenv/bin/python 专八/tools/pron_check.py            # 检查全部篇目；有未登记或音标变化的词，退出码非 0
    /opt/ttsenv/bin/python 专八/tools/pron_check.py --approve  # 人工核对无误后登记当前全部词的音标
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parent.parent
sys.path[:0] = [str(R / 'tools' / 'tts'), str(HERE)]
import make_audio as M  # noqa: E402
from misaki import en  # noqa: E402

REG = HERE / '专名读音已核.json'


def collect():
    pron = M.G.Pronouncer()
    g2p = en.G2P(trf=False, british=False)
    P = {p['id']: p for p in json.loads((R / '专八' / 'data' / 'vocab.json').read_text('utf-8'))['passages']}
    out = {}
    for pid, p in sorted(P.items()):
        for k, s in enumerate([x for pa in p['paras'] for x in pa], 1):
            key = f'{pid}:{k}'
            for w in pron.WORD.findall(pron.read_text(s['en'], key)):
                if w not in out and ('❓' in g2p(w)[0] or w in pron.lexicon or w in pron.sentence.get(key, {})):
                    out[w] = {'音标': pron.phonemes(w, key), '首见': key}
    return out


def main():
    cur = collect()
    if '--approve' in sys.argv:
        REG.write_text(json.dumps(cur, ensure_ascii=False, indent=1) + '\n', 'utf-8')
        print(f'已登记 {len(cur)} 个词')
        return
    reg = json.loads(REG.read_text('utf-8')) if REG.exists() else {}
    bad = [(w, v) for w, v in cur.items() if reg.get(w, {}).get('音标') != v['音标']]
    for w, v in bad:
        print(f'未核：{v["首见"]} {w}  音标 {v["音标"]}（登记的是 {reg.get(w, {}).get("音标")}）')
    print('全部已核' if not bad else f'{len(bad)} 个词的读音没有人工核对过')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
