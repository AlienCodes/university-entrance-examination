"""Verify the spoken name in the cinnamon reading against two American dictionary recordings."""
from functools import lru_cache
from pathlib import Path
import tempfile

import numpy as np

from aiden_boundaries import RATE, interior_gaps, words

GUIDES = {
    "Cambridge": "https://dictionary.cambridge.org/pronunciation/english/ceylonese",
    "Merriam-Webster": "https://www.merriam-webster.com/dictionary/Ceylonese",
}
HINT = ("Pronounce Ceylonese as see-luh-NEEZ, /ˌsiːləˈniːz/. "
        "Link the three syllables naturally, with the strongest stress on NEEZ.")
PHONES = {
    "see-luh-neez": "S IY L AH N IY Z", "say-luh-neez": "S EY L AH N IY Z",
    "sell-luh-neez": "S EH L AH N IY Z", "sil-oh-neez": "S IH L AA N IY Z",
    "see-lone-eez": "S IY L AA N IY Z", "say-lone-eez": "S EY L AA N IY Z",
    "see-luh-nees": "S IY L AH N IY S", "say-luh-nees": "S EY L AH N IY S",
    "sil-oh-nees": "S IH L AA N IY S", "see-lone-ees": "S IY L AA N IY S",
    "say-lone-ees": "S EY L AA N IY S", "celine": "S AH L IY N",
    "ceylon": "S IH L AA N", "sneeze": "S N IY Z", "silly": "S IH L IY",
    "knees": "N IY Z", "ceiling": "S IY L IH NG", "chinese": "CH AY N IY Z",
    "selenium": "S AH L IY N IY AH M", "seas": "S IY Z", "sail": "S EY L",
    "sails": "S EY L Z",
    "see-luh-nee": "S IY L AH N IY", "say-luh-nee": "S EY L AH N IY",
    "see-luh": "S IY L AH", "say-luh": "S EY L AH", "luh-neez": "L AH N IY Z",
}


@lru_cache(maxsize=1)
def phone_recognizer():
    from pocketsphinx import Decoder, get_model_path

    with tempfile.TemporaryDirectory() as tmp:
        dictionary = Path(tmp) / "word.dict"
        grammar = Path(tmp) / "word.gram"
        phones = {**PHONES, "the": "DH AH", "native": "N EY T IH V"}
        dictionary.write_text("".join(f"{word} {pron}\n" for word, pron in phones.items()))
        grammar.write_text("#JSGF V1.0;\ngrammar name;\npublic <reading> = [the] ("
                           + " | ".join(PHONES) + ") [native];\n")
        return Decoder(hmm=str(Path(get_model_path()) / "en-us/en-us"), dict=str(dictionary),
                       jsgf=str(grammar), samprate=RATE, loglevel="ERROR")


def locate(transcript, expected):
    """Match every surrounding word. Only the name can have a different ASR spelling."""
    index = expected.index("ceylonese")
    before, after = expected[:index], expected[index + 1:]
    end = len(transcript) - len(after)
    if (transcript[:index] != before or transcript[end:] != after or not 1 <= end - index <= 3
            or transcript[index][0] not in "sc"):
        raise ValueError("The two sides of Ceylonese or its onset differ from the printed phrase")
    return index, end


def timed_words(audio):
    from 听对 import recognizer

    decoder = recognizer()
    stream = decoder.create_stream()
    padding = 2400
    stream.accept_waveform(RATE, np.pad(audio, (padding, padding)).astype("float32"))
    decoder.decode_stream(stream)
    tokens = []
    for token, timestamp in zip(stream.result.tokens, stream.result.timestamps):
        if not tokens or token.startswith((" ", "▁")):
            tokens.append([token.lstrip(" ▁"), round(timestamp * RATE) - padding])
        else:
            tokens[-1][0] += token
    return [(item, t) for raw, t in tokens for item in words(raw)]


def verify(audio, text, first, second):
    expected = words(text)
    if expected.count("ceylonese") != 1:
        raise ValueError("Expected one occurrence of Ceylonese")
    endings = []
    for hypothesis in (first, second):
        heard = words(hypothesis)
        _, last = locate(heard, expected)
        endings.append(heard[last - 1])
    if not any(ending.endswith(("se", "ze", "s", "z")) for ending in endings):
        raise ValueError("Neither independent transcription heard the ending of Ceylonese")
    timed = timed_words(audio)
    begin, end = locate([item for item, _ in timed], expected)
    lo = max(0, timed[begin][1] - round(.09 * RATE))
    hi = min(len(audio), timed[end][1] + round(.03 * RATE)) if end < len(timed) else len(audio)
    sample = audio[lo:hi]
    padding = 2400
    signal = np.pad(sample, (padding, padding))
    decoder = phone_recognizer()
    decoder.start_utt()
    decoder.process_raw((np.clip(signal, -1, 1) * 32767).astype("<i2").tobytes(), False, True)
    decoder.end_utt()
    found = [s for s in (decoder.seg() or ()) if s.word in PHONES]
    if (len(found) != 1 or found[0].word not in ("see-luh-neez", "say-luh-neez")
            or found[0].prob < .40):
        raise ValueError(f"Ceylonese differs from the selected dictionary readings: {[s.word for s in found]}")
    segment = found[0]
    start = lo + max(0, segment.start_frame * 160 - padding)
    stop = lo + min(len(sample), (segment.end_frame + 1) * 160 - padding)
    if not .36 * RATE <= stop - start <= 1.6 * RATE:
        raise ValueError("Duration of Ceylonese is inconsistent with the three-syllable word")
    if any(start < (a + b) / 2 < stop for a, b in interior_gaps(audio)):
        raise ValueError("An internal acoustic pause interrupts Ceylonese")
    return {"dictionary_reading": segment.word, "score": round(segment.prob, 3),
            "start": round(start / RATE, 3), "end": round(stop / RATE, 3)}
