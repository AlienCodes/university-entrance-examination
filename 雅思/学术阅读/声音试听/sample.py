"""Audition the official English Qwen speakers on one unchanged IELTS paragraph."""
import argparse
import json
import os
import time
from pathlib import Path

MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
REVISION = "0c0e3051f131929182e2c023b9537f8b1c68adfe"
DIRECTION = (
    "Read to one interested adult listener in clear, relaxed American English. "
    "Use the cadence of a thoughtful science documentary. Group words by meaning. "
    "Let parenthetical remarks sit lightly within the sentence. Give dates and names "
    "clear diction. Speak at a comfortable listening pace, without sales-like emphasis."
)
READINGS = {
    "8 June 2004": "the eighth of June, two thousand and four",
    "6 December 1882": "the sixth of December, eighteen eighty-two",
}


def passage():
    source = Path(__file__).resolve().parents[1] / "原稿" / "C9T2P2.json"
    printed = json.loads(source.read_text())["paragraphs"][1]
    assert len(printed) == 5 and printed[0].startswith("On 8 June 2004,")
    spoken = []
    for sentence in printed:
        for paper, words in READINGS.items():
            sentence = sentence.replace(paper, words)
        spoken.append(sentence.replace(" - ", " — "))
    return printed, spoken


def main():
    import numpy as np
    import soundfile as sf
    import torch
    from huggingface_hub import snapshot_download
    from qwen_tts import Qwen3TTSModel

    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--speakers", nargs="+", choices=["Aiden", "Ryan"], default=["Aiden", "Ryan"])
    args = parser.parse_args()
    torch.set_num_threads(min(4, len(os.sched_getaffinity(0))))
    model_dir = snapshot_download(MODEL, revision=REVISION)
    model = Qwen3TTSModel.from_pretrained(model_dir, dtype=torch.float32, device_map="cpu", attn_implementation="sdpa")
    printed, spoken = passage()
    for voice in args.speakers:
        path = args.output / voice.lower()
        path.mkdir(parents=True, exist_ok=True)
        info = {"model": MODEL, "revision": REVISION, "speaker": voice, "direction": DIRECTION, "sentences": []}
        for number, (text, script) in enumerate(zip(printed, spoken), 1):
            torch.manual_seed(24830 + number)
            start = time.monotonic()
            with torch.inference_mode():
                waves, sr = model.generate_custom_voice(text=script, speaker=voice, language="English",
                                                       instruct=DIRECTION, max_new_tokens=500)
            wave = np.asarray(waves[0], dtype=np.float32)
            if not np.isfinite(wave).all() or not 1.5 < len(wave) / sr < 35:
                raise ValueError(f"Unexpected audio data in {voice} sentence {number}")
            sf.write(path / f"{number}.wav", wave, sr)
            timing = {"sentence": number, "printed": text, "spoken": script, "duration": round(len(wave)/sr, 3),
                      "cpu_seconds_elapsed": round(time.monotonic()-start, 2)}
            info["sentences"].append(timing)
            print(voice, timing["sentence"], timing["duration"], timing["cpu_seconds_elapsed"], flush=True)
        (path / "run.json").write_text(json.dumps(info, ensure_ascii=False, indent=2)+"\n")


if __name__ == "__main__":
    main()
