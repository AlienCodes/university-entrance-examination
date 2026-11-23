"""Measure the production voice and recognizer separately on a specified printed sentence."""
import argparse
import json
import os
from pathlib import Path
import resource
import time
from unittest.mock import patch

from audio_lesson import LESSON, PID, Reader, cet, load
import aiden_audio
from aiden_profile import IDENTITY
from lesson import save


def measure(number, output):
    sentences = [row['en'] for paragraph in load()['paras'] for row in paragraph]
    original = sentences[number - 1]
    reader = Reader()
    reader.lexicon.update(json.loads((LESSON / '篇目信息.json').read_text())['pronunciation'])
    config = json.loads((cet.G.HERE / 'voices.json').read_text())[cet.VOICE]
    key = f'{PID}:{number}'
    reading = reader.read_text(original, key)
    engine = aiden_audio.Aiden()
    result = dict(lesson=PID, sentence=number, model=IDENTITY, text=original, read=reading,
                  groups=cet.narration_phrases(reading, key, config['clause_pause']),
                  cores=len(os.sched_getaffinity(0)), calls=[])
    generate = engine.render
    recognize = aiden_audio.recognize

    def timed_render(text, seed, pron):
        now = time.monotonic()
        wav = generate(text, seed, pron)
        row = dict(phase='generate', seed=seed, seconds=round(time.monotonic()-now, 3),
                   audio_seconds=round(len(wav)/24000, 3), text=text)
        result['calls'].append(row)
        save(output, result)
        print(row, flush=True)
        return wav

    def timed_recognize(wav):
        now = time.monotonic()
        transcript, tokens = recognize(wav)
        row = dict(phase='recognize', seconds=round(time.monotonic()-now, 3), transcript=transcript)
        result['calls'].append(row)
        save(output, result)
        print(row, flush=True)
        return transcript, tokens

    start = time.monotonic()
    try:
        with patch.object(engine, 'render', timed_render), patch.object(aiden_audio, 'recognize', timed_recognize):
            audio, spans = engine.sentence(reading,key,engine,reader,engine.style(config['style']),config['speed'],config)
        result.update(passed=True, review=engine.review[key], seconds_of_sentence=len(audio)/cet.G.SR,
                      measured_groups=len(spans))
    except Exception as error:
        result.update(passed=False, error=f'{type(error).__name__}: {error}')
        raise
    finally:
        result.update(wall_seconds=round(time.monotonic()-start,3),
                      max_rss_gib=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20,3))
        save(output, result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('sentence', type=int)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    measure(args.sentence, args.output)
