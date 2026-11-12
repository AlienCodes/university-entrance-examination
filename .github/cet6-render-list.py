"""写 .github/cet6-render.txt（提交推送后由 render-cet6-chalk.yml 在 GitHub 上生成）：列出还没有可用成品的篇目——
仓库里没提交的（git ls-files + make_video.video_name），以及提交了但不能用的：核查结果不是全部通过、指纹与现在的截图审阅登记不同
（如 s47：07:18 重新审阅登记之前 03:40 做的样片，本机批量脚本见到已提交就跳过，它不会被重做）、体积与核查时不同。

    /opt/ttsenv/bin/python .github/cet6-render-list.py [运行标签]      # 默认标签 cet6-chalk-full-1；以 test 开头 = 试跑不发布，probe = 只查截图
    然后：git add .github/cet6-render.txt && git commit -m … -- .github/cet6-render.txt && git push
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '六级' / 'tools'))
import make_video as M  # noqa: E402  六级入口（= 专八/tools/make_video.py --project 六级）


def git(*a):
    return subprocess.run(['git', '-C', str(ROOT), '-c', 'core.quotepath=off', *a], capture_output=True, text=True, check=True).stdout


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else 'cet6-chalk-full-1'
    P = json.loads((ROOT / '六级' / 'data' / 'vocab.json').read_text('utf-8'))['passages']
    reg = json.loads(M.SAMPLE_REG.read_text('utf-8'))
    tracked = set(git('ls-files', '-z', '--', '六级/最终视频_黑板').split('\0'))
    todo, ok = [], []
    for p in P:
        name = M.video_name(p)
        path = f'六级/最终视频_黑板/{name}'
        rep = ROOT / '六级' / '样片' / '成品核查' / (Path(name).stem + '_核查.json')
        why = ''
        if path not in tracked:
            why = '没提交'
        elif not rep.exists():
            why = '没有核查结果'
        else:
            r = json.loads(rep.read_text('utf-8'))
            size = int(git('cat-file', '-s', f'HEAD:{path}'))       # 已提交的视频多半已移出工作区（sparse-checkout），按仓库里的大小核对
            if not r.get('ok'):
                why = '核查不是全部通过'
            elif r.get('指纹') != reg.get(f'{p["id"]}@3', {}).get('指纹'):
                why = f'指纹 {r.get("指纹")} ≠ 审阅登记 {reg.get(p["id"] + "@3", {}).get("指纹")}'
            elif r.get('size') != size:
                why = '体积与核查时不同'
        (todo if why else ok).append(p['id'])
        if why and why != '没提交':
            print(f'{p["id"]}：已提交但不能用（{why}），重新生成', file=sys.stderr)
    (ROOT / '.github' / 'cet6-render.txt').write_text('\n'.join([tag, *todo]) + '\n', 'utf-8')
    print(f'可用的已提交成品 {len(ok)} 篇：{" ".join(ok)}', file=sys.stderr)
    print(f'要生成 {len(todo)} 篇，已写 .github/cet6-render.txt（标签 {tag}）', file=sys.stderr)


if __name__ == '__main__':
    main()
