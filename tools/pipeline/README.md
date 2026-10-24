# 复核与制作流程脚本

完整用法与顺序见仓库根目录的 `交接文档.md` 第 4、5 节。这里只记录“审阅文件”的格式和导出方法。

## 英文审阅文件（第 1 步，deep-english.js 的输入）

```python
import json, os
S = json.load(open('tools/sents.json'))
os.makedirs('SP/en', exist_ok=True)
for o in S:
    if o['id'] not in PIDS:
        continue
    L = [f"# {o['id']} {o['year']} {o['paper']} 阅读{o['part']}", '']
    k = 0
    for para in o['sents']:
        for s in para:
            k += 1
            L.append(f'[{k}] EN: {s}')
        L.append('')
    open(f"SP/en/{o['id']}.txt", 'w').write('\n'.join(L))
```

`annotate.js` 的输入 `SP/en_final/pXX.txt` 格式相同，内容用英文订正之后的 `sents.json`。

## 译文审阅文件（第 3 步）

`python3 tools/pipeline/gen_review.py SP/rvN`：为全部已完成篇目生成 `pXX.txt`，内容包括标题、体裁、概要，逐句 `[n] EN`、`ZH`，以及每个词条（词头、分级、释义、高亮原文）。

## 埋雷（终审必做）

把要复核的篇目从 `SP/rvN` 复制到 `SP/fzN`，在其中 2 篇各做 6 处确定错误的替换，替换目标必须恰好出现一次。之后对 `SP/fzN` 跑 `workflows/audit_zh3.js`，12 处必须全部出现在 kept 里。真实篇目里的其他发现照常处理。
