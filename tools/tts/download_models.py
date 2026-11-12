"""下载模型到 tools/tts/models/（都在 GitHub 上）。加 --qa 同时下载自检用的模型。"""
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

M = Path(__file__).resolve().parent / 'models'
KOKORO = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/'
ASR = 'https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8.tar.bz2'


def get(url, dest):
    if dest.exists():
        print('已存在', dest.name)
        return
    print('下载', url)
    tmp = dest.with_suffix(dest.suffix + '.part')
    urllib.request.urlretrieve(url, tmp)
    tmp.rename(dest)


def main():
    M.mkdir(exist_ok=True)
    for f in ('kokoro-v1.0.onnx', 'voices-v1.0.bin'):
        get(KOKORO + f, M / f)
    if '--qa' in sys.argv:
        if not any(M.glob('sherpa-onnx-nemo-parakeet*')):
            arc = M / 'parakeet.tar.bz2'
            get(ASR, arc)
            with tarfile.open(arc) as t:
                t.extractall(M)
            arc.unlink()
        if not (M / 'SpeechMOS').exists():
            subprocess.run(['git', 'clone', '--depth', '1', '--branch', 'v1.2.0',
                            'https://github.com/tarepan/SpeechMOS', str(M / 'SpeechMOS')], check=True)
    print('模型已就绪：', M)


if __name__ == '__main__':
    main()
