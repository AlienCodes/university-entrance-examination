"""Check the two words of the isolated botanical name in Cambridge 12, Test 5, Passage 1."""
from functools import lru_cache
from pathlib import Path
import re
import tempfile

# NC State Extension and Oregon State University both give KWER-kus SOO-ber.
NAME = "Quercus suber"
HINT = "Pronounce the botanical name Quercus suber as KWER-kus SOO-ber."
GUIDES = [
    "https://plants.ces.ncsu.edu/plants/quercus-suber/",
    "https://landscapeplants.oregonstate.edu/plants/quercus-suber",
]
# Compete against the misreadings heard in production as well as missing syllables.
GENUS_PRONUNCIATIONS = {
    "quercus": "K W ER K AH S", "kerkuss": "K ER K AH S", "corkus": "K AO R K AH S",
    "prickus": "P R IH K AH S", "quirk": "K W ER K", "crocus": "K R OW K AH S", "kirk": "K ER K",
}
SPECIES_PRONUNCIATIONS = {
    "suber": "S UW B ER", "super": "S UW P ER", "subaru": "S UW B ER UW", "subar": "S UW B AA R",
    "suburshort": "S AH B ER", "simmer": "S IH M ER", "simber": "S IH M B ER", "soo": "S UW", "bur": "B ER",
}


@lru_cache(maxsize=1)
def phone_recognizer():
    from pocketsphinx import Decoder, get_model_path

    with tempfile.TemporaryDirectory() as tmp:
        dictionary = Path(tmp) / "words.dict"
        grammar = Path(tmp) / "name.gram"
        phones = {**GENUS_PRONUNCIATIONS, **SPECIES_PRONUNCIATIONS}
        dictionary.write_text("".join(f"{word} {pron}\n" for word, pron in phones.items()))
        genus = " | ".join(GENUS_PRONUNCIATIONS)
        species = " | ".join(SPECIES_PRONUNCIATIONS)
        grammar.write_text(f"#JSGF V1.0;\ngrammar oak;\npublic <name> = ({genus}) ({species});\n")
        return Decoder(hmm=str(Path(get_model_path()) / "en-us/en-us"), dict=str(dictionary),
                       jsgf=str(grammar), samprate=16000, loglevel="ERROR")


def verify(audio, first, second, gaps):
    import numpy as np

    # The human university recording also decodes as 'Quercus Subur' or
    # 'Quercus Subaru'. Use the unprompted recognizers for the genus and
    # require the acoustic decoder to distinguish SOO-ber from super/Subaru.
    heard = [re.findall(r"[a-z]+", transcript.lower()) for transcript in (first, second)]
    if not any(row and row[0] in {"quercus", "quircus", "quirkus"} for row in heard):
        raise ValueError("Botanical genus is unclear in the unconstrained recognition")
    rec = phone_recognizer()
    padding = 1600
    signal = np.pad(audio, (padding, padding))
    rec.start_utt()
    rec.process_raw((np.clip(signal, -1, 1) * 32767).astype("<i2").tobytes(), False, True)
    rec.end_utt()
    words = [seg for seg in (rec.seg() or ()) if not seg.word.startswith("<")]
    if (len(words) != 2 or words[0].word not in {"quercus", "corkus"} or words[1].word != "suber"
            or min(seg.prob for seg in words) < .40):
        raise ValueError(f"Botanical name differs from KWER-kus SOO-ber: {[s.word for s in words]}")
    spans = [(max(0, seg.start_frame * 160 - padding),
              min(len(audio), (seg.end_frame + 1) * 160 - padding)) for seg in words]
    for start, end in spans:
        if end - start < 1600:
            raise ValueError("A syllable of the botanical name is too short")
    for start, end in gaps:
        centre = (start + end) // 2
        if not spans[0][1] - 1000 <= centre <= spans[1][0] + 1000:
            raise ValueError("A pause falls within a word of the botanical name")
    # An omitted prefix or suffix must not disappear into the decoder's silence.
    for margin in (audio[:max(0, spans[0][0] - 1600)], audio[min(len(audio), spans[1][1] + 1600):]):
        blocks = margin[:len(margin) // 400 * 400].reshape(-1, 400)
        if len(blocks) and np.max(np.mean(blocks.astype("float64") ** 2, axis=1)) > 1.e-4:
            raise ValueError("There is unaccounted speech outside the two botanical words")
    return {"expected": "KWER-kus SOO-ber", "heard": [s.word for s in words],
            "spans_seconds": [[round(x / 16000, 3) for x in pair] for pair in spans],
            "confidence": [round(s.prob, 3) for s in words], "references": GUIDES}
