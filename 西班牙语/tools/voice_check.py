"""音色能不能用：模型文件、参考录音、Python 包。batch.py（开工前检查、--check 安装自检、--list）和
make_audio.py（开始合成前）共用这一份，免得一处查了、另一处没查，合成到一半才冒出一大段英文报错。只用标准库。

    import voice_check
    voice_check.voice_problems(cfg)   # cfg = voices.json 里一个音色的设置；返回问题列表（空 = 能用）
    voice_check.fix_hint(cfg)         # 给老师看的处理办法
"""
import importlib.util
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ES = HERE.parent

MODULES = {'sherpa.py': ['sherpa_onnx'], 'qwen3tts.py': ['torch', 'transformers', 'qwen_tts', 'librosa'],
           'kokoro_worker.py': ['kokoro_onnx']}      # 各引擎脚本要的 Python 包（numpy、soundfile 等基本包由安装自检另查）


def _abs(p):
    p = Path(p)
    return p if p.is_absolute() else ES / p


def missing_modules(mods, python=None):
    """mods 里哪些包装不上（找不到）。python 为空 = 当前这个 Python；否则到那个 Python 里查（不导入，只找）。
    那个 Python 运行不了时返回 None。"""
    if not python:
        return [m for m in mods if importlib.util.find_spec(m) is None]
    code = 'import importlib.util, sys; print(" ".join(m for m in sys.argv[1:] if importlib.util.find_spec(m) is None))'
    try:
        r = subprocess.run([python, '-c', code, *mods], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.split() if r.returncode == 0 else None


def voice_problems(cfg):
    """这个音色能不能用。返回问题列表（空 = 能用）。"""
    probs = []
    if cfg.get('engine') == 'worker':
        md = _abs(cfg.get('model_dir', ''))
        script = cfg.get('script')
        if not (HERE / 'engines' / str(script)).is_file():
            probs.append(f'找不到合成程序 西班牙语/tools/engines/{script}')
        need = {'sherpa.py': ['tts.json', 'voice.bin', 'vocoder.int8.onnx'] if cfg.get('kind') == 'supertonic' else [],
                'qwen3tts.py': ['model.safetensors', 'speech_tokenizer/config.json']}.get(script, [])
        miss = [f for f in need if not (md / f).is_file()]
        if not cfg.get('model_dir') or not md.is_dir() or miss:
            probs.append(f'模型没装好：{md}' + (f' 缺 {miss}' if md.is_dir() else ' 不存在'))
        if cfg.get('ref_audio') and not _abs(cfg['ref_audio']).is_file():
            probs.append(f'找不到参考录音 {_abs(cfg["ref_audio"])}')
        mods = MODULES.get(script, [])
        py = cfg.get('python')
        if py in (None, '', 'auto'):
            lack = missing_modules(mods)
        elif not Path(py).exists() and not shutil.which(py):
            probs.append(f'找不到 Python {py}')
            lack = []
        else:
            lack = missing_modules(mods, py)
            if lack is None:
                probs.append(f'Python {py} 运行不了')
                lack = []
        if lack:
            probs.append(f'缺少 Python 包 {lack}')
    elif cfg.get('engine') == 'kokoro':
        if importlib.util.find_spec('kokoro_onnx') is None:
            probs.append('缺少 Python 包 kokoro_onnx')
        m = ES.parent / 'tools' / 'tts' / 'models'
        lack = [f for f in ('kokoro-v1.0.onnx', 'voices-v1.0.bin') if not (m / f).is_file()]
        if lack:
            probs.append(f'缺少 Kokoro 模型 tools/tts/models/ 里的 {lack}')
    else:
        probs.append(f'voices.json 里的 engine 写的是 {cfg.get("engine")!r}，只能是 worker 或 kokoro')
    return probs


def fix_hint(cfg):
    if cfg.get('script') == 'qwen3tts.py':
        return ('Qwen3 配音需要另外安装：①运行安装脚本时加 --qwen3（Windows：install_windows.bat -Qwen3）装 PyTorch 等；'
                '②下载 Release 里的 qwen3-tts-1.7b-base.zip.001、.002 … 放进工具包文件夹，运行 python 西班牙语/tools/join_parts.py 解压模型。'
                '或者先用快速的 Supertonic 音色：--voice supertonic3_M1F5_25')
    return '请重新运行安装脚本（install.sh / install_windows.bat），看 使用说明.md「安装」'
