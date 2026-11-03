"""合成结果是否齐全（踩坑 98）：任务里每个 take 都要有 meta_part*.json，缺的打印出来（空输出 = 齐全）。
合成机中途被停（exit 143）时 collect 照样发布，只少一个 take；不查就会悄悄少候选。
用法：python3 高考续写/tools/合成齐全.py <runs/任务-运行号> <音色 id> <任务文件>   （读 origin/gram-tts-out 的文件列表）"""
import json
import subprocess
import sys


def missing(paths, run, voice, takes):
    return [f'take{k}' for k in takes
            if not any(p.startswith(f'{run}/{voice}/take{k}/meta_part') for p in paths)]


def main():
    run, voice, task = sys.argv[1:4]
    paths = subprocess.run(['git', '-c', 'core.quotepath=false', 'ls-tree', '-r', '--name-only',
                            'origin/gram-tts-out', f'{run}/{voice}/'],
                           capture_output=True, text=True, check=True).stdout.split('\n')
    print(' '.join(missing(paths, run, voice, json.load(open(task, encoding='utf-8'))['takes'])))


if __name__ == '__main__':
    main()
