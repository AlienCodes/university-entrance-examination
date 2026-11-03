"""合成结果是否齐全（踩坑 98）：任务里每个 take 的每个 part（0…parts-1）都要有 meta_part<p>.json，缺的打印出来（空输出 = 齐全）。
合成机中途被停（exit 143）时 collect 照样发布，只少一个 take；不查就会悄悄少候选。
用法：python3 高考续写/tools/合成齐全.py <runs/任务-运行号> <音色 id> <任务文件>   （读 origin/gram-tts-out 的文件列表）"""
import json
import subprocess
import sys


def missing(paths, run, voice, takes, parts=1):
    have = set(paths)
    return [f'take{k}' + (f'/part{p}' if parts > 1 else '') for k in takes for p in range(parts)
            if f'{run}/{voice}/take{k}/meta_part{p}.json' not in have]


def main():
    run, voice, task = sys.argv[1:4]
    paths = subprocess.run(['git', '-c', 'core.quotepath=false', 'ls-tree', '-r', '--name-only',
                            'origin/gram-tts-out', f'{run}/{voice}/'],
                           capture_output=True, text=True, check=True).stdout.split('\n')
    t = json.load(open(task, encoding='utf-8'))
    print(' '.join(missing(paths, run, voice, t['takes'], t.get('parts', 1))))


if __name__ == '__main__':
    main()
