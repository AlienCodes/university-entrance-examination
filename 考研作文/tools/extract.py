"""考研作文范文 → 句子（供翻译、标注、音频、视频使用）。

    /opt/ttsenv/bin/python 考研作文/tools/extract.py

输入 考研/作文/2026.json … 2021.json（范文定稿，三轮复核），输出 考研作文/作文/sents.json：
[{id, year, paper, passage, part, words, prompt_img, lead, sents: [[段1句1, …], …], letter?}]
编号 w01 = 2026 年考研英语一 Part A，w02 = 英语一 Part B，w03 = 英语二 Part A，w04 = 英语二 Part B，w05 = 2025 年……（从新到旧，同一年英语一在前）。
切句用考研阅读的 split（保护缩写、人名首字母），逐段校验句子拼回去与原段落完全一致。
lead = 第一句开口时刻：片头 1.5 秒 + 原题屏 PROMPT 秒（两段都静音）；音频（make_audio.py）和视频（make_video）都从这里取，不各写一份。
书信的称呼单独一段、结束语 + 署名一段；通知的标题、署名各一段（letter 里另记原样）。
"""
import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE.parent
ROOT = C.parent
PROMPT = 2.0           # 原题屏停留秒数（静音）；用户 2026-10-22 看过样片：10 秒太长，改成 2 秒
_spec = importlib.util.spec_from_file_location('ky_split', ROOT / '考研' / 'tools' / 'split_sents.py')
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
split = _m.split


def count(sents):
    """片头“全文 N 词”：与 build_vocab 的复算规则相同（空白、破折号、省略号切分，含字母或数字的才算）。"""
    return len([w for w in re.split(r'[\s—–…]+', ' '.join(s for para in sents for s in para)) if re.search(r'[A-Za-z0-9]', w)])


def main():
    out, n = [], 0
    for y in ('2026', '2025', '2024', '2023', '2022', '2021'):
        for e in json.loads((ROOT / '考研' / '作文' / f'{y}.json').read_text('utf-8')):
            n += 1
            pid = f'w{n:02d}'
            # 书信、通知的格式行（用户 2026-10-22 说剩下的全部做完，格式由协调人定，事后汇报）：称呼单独一屏（Dear Paul,），
            # 结束语和署名合成最后一屏（Yours, Li Ming）；通知的标题第一屏、署名最后一屏（Li Ming）。都朗读、都标生词（铁律 1）
            paras = list(e['body'])
            if e.get('title'):
                paras = [e['title']] + paras
            if e.get('salutation'):
                paras = [e['salutation']] + paras
            if e.get('closing'):
                paras.append(f"{e['closing']} {e['signature']}")
            elif e.get('signature'):
                paras.append(e['signature'])
            sents = []
            for para in paras:
                ss = split(para)
                assert ' '.join(ss) == para, (pid, para[:80])
                sents.append(ss)
            part = e['part'].split()[-1]
            # paper “2026年考研英语一 写作”、passage “Part B”：片头副标题里 passage 用英文斜体（Nunito，没有中文字形），中文“写作”放在 paper 里
            # （w02 截图检查：“写作”落到系统字体 WenQuanYi）；文件名仍是“2026年考研英语一 写作 Part B 题目.mp4”；pdf = 原卷文件名
            rec = {'id': pid, 'src': e['id'], 'year': int(y), 'paper': f"{e['paper']} 写作", 'passage': f'Part {part}', 'part': part, 'pdf': e['paper'],
                   'words': count(sents), 'prompt_img': f'{pid}.png', 'lead': round(1.5 + PROMPT, 3), 'sents': sents}
            if e.get('salutation') or e.get('title'):
                rec['letter'] = {k: e[k] for k in ('title', 'salutation', 'closing', 'signature') if e.get(k)}
            out.append(rec)
    (C / '作文').mkdir(exist_ok=True)
    (C / '作文' / 'sents.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), 'utf-8')
    print(f'{len(out)} 篇，{sum(len(s) for r in out for s in r["sents"])} 句')


if __name__ == '__main__':
    main()
