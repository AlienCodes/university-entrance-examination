"""Replay the reported broken word and the repaired word extracted from the two published MP4s."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "雅思/学术阅读"
EVIDENCE = PROJECT / "审校/Aiden词内断音"
sys.path.insert(0, str(PROJECT / "tools"))
from aiden_boundaries import RATE, independent, reference, verify_join, verify_reference, words
from aiden_encoded_audio import compare_waveforms
from aiden_word_review import same_words


def rejects(check, *args):
    try:
        check(*args)
    except ValueError:
        return
    raise AssertionError("A known broken phrase was accepted")


def recorded_join(edition, listen):
    record = json.loads((EVIDENCE / f"{edition}证据.json").read_text())
    clip = EVIDENCE / f"{edition}第3句停顿.flac"
    assert hashlib.sha256(clip.read_bytes()).hexdigest() == record["sha256"]
    phrases = record["observed"]
    assert len(phrases) == len(record["clip_16khz"]) == 2
    if listen:
        import soundfile as sf

        raw, rate = sf.read(clip, dtype="float32")
        assert rate == RATE
        for phrase, (start, end) in zip(phrases, record["clip_16khz"], strict=True):
            assert 0 <= start < end <= len(raw)
            phrase["second_heard"] = independent(raw[start:end])
    return record


def main(listen):
    old = recorded_join("旧版", listen)
    revised = recorded_join("修订版", listen)
    assert old["source_video_sha256"] != revised["source_video_sha256"]
    rejects(verify_join, *old["observed"])

    left, right = revised["observed"]
    verify_join(left, right)
    # One complete bordering word cannot make up for the other being clipped.
    rejects(verify_join, dict(text="export sectors", second_heard="export se"), right)
    rejects(verify_join, left, dict(text="which make products", second_heard="make products"))
    for written, heard in (("appreciate the mathematical way", "appreciate mathematical way"),
                           ("with modelled birds", "with model birds"),
                           ("they did not return", "they did return"), ("walked", "walk")):
        assert not same_words(words(written), words(heard))
    assert same_words(words("with modelled birds"), words("with modeled birds"))
    for printed, recognized in (("artefacts", "artifacts"), ("sceptical", "skeptical"),
                                ("unravelling", "unraveling"), ("counter-productive", "counterproductive"),
                                ("Counter-intuitively", "Counterintuitively"),
                                ("travelled to north-western India", "traveled to northwestern India"),
                                ("south-western Tanzania", "southwestern Tanzania"),
                                ("terrestrial re-tooling", "terrestrial retooling"),
                                ("skilful cork-strippers prise away a semi-circular husk",
                                 "skillful corkstrippers prize away a semicircular husk")):
        assert same_words(words(printed), words(recognized))
        assert same_words(words(recognized), words(printed))
    for printed, recognized in (("it is now evident", "it is no evident"),
                                ("artefacts", "artifact"), ("unravelling", "unravelled"),
                                ("north-western", "north-eastern"), ("nowhere", "now here"),
                                ("cork-strippers", "cork stripper"), ("Makete", "Makati")):
        assert not same_words(words(printed), words(recognized))
    assert words(left["second_heard"])[-2:] == ["export", "sectors"]
    assert words(right["second_heard"])[:1] == ["which"]
    left_end = revised["clip_16khz"][0][1]
    right_start = revised["clip_16khz"][1][0]
    assert abs((right_start - left_end) / RATE - 0.28) < 0.003

    previous = [{"text": written, "second_heard": heard}
                for written, heard in old["single_word_previous_sentence"]]
    verify_join(*previous)
    sample = np.random.default_rng(235).normal(0, 0.08, 24000).astype("float32")
    ref = reference(sample)
    verify_reference(sample * 0.81, ref)
    compare_waveforms(sample, sample * 0.97)
    muted = sample.copy()
    muted[10000:14480] = 0
    for damaged in (muted, sample[:-4480]):
        rejects(verify_reference, damaged, ref)
        rejects(compare_waveforms, sample, damaged)
    print("旧版 sectors 断音、人工静音及截短均已拦截。修订版两个完整词和词间停顿均已核对。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", action="store_true")
    main(parser.parse_args().audio)
