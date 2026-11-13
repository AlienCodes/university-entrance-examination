"""整套组装的定点反例：原样PCM/真采样点、信号保护、音量/SNR/秒级门禁。"""
import hashlib
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('full_engine_test', HERE / '整套精听.py')
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)
from 精听数据 import float_wav


class FullAssemblyChecks(unittest.TestCase):
    def test_native_pcm_and_one_sample_interval_tampering(self):
        # 11025Hz/30 has half-sample frame boundaries; no resampling is permissible.
        sr = 11025
        rng = np.random.default_rng(174)
        x = rng.uniform(-.3, .3, (sr * 12, 2)).astype('float32')
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            sf.write(td / 'source.wav', x, sr, subtype='FLOAT')
            records = []
            for k, ident in enumerate(['2009-A', '2009-B1', '2009-B2']):
                intervals = [(round((k + .01131) * sr), round((k + .81237) * sr)),
                             (round((k + .90123) * sr), round((k + 1.20679) * sr))]
                body = np.concatenate([x[a:b] for a, b in intervals])
                duration = math.ceil((e.LEAD + len(body) / sr + e.TAIL) * e.FPS) / e.FPS
                y = np.zeros((round(duration * sr), 2), dtype='float32')
                lead = round(e.LEAD * sr)
                y[lead:lead + len(body)] = body
                trusted = td / (ident + '-trusted.wav')
                float_wav(trusted, y, sr)
                records.append({'id': ident, 'tm': {'sample_rate': sr, 'channels': 2, 'duration': duration,
                                'kept_intervals': [[a / sr, b / sr] for a, b in intervals],
                                'audio_sha256': e.sha(trusted)}})
            report = e.reconstruct(records, td / 'source.wav', td / 'pcm')
            ref = np.concatenate([sf.read(td / (r['id'] + '-trusted.wav'), dtype='float32', always_2d=True)[0]
                                  for r in records])
            actual, native = sf.read(td / 'pcm' / report['file'], dtype='float32', always_2d=True)
            self.assertEqual(native, sr)
            self.assertTrue(np.array_equal(actual, ref))
            self.assertEqual(report['pcm_sha256'], hashlib.sha256(ref.astype('<f4').tobytes()).hexdigest())
            records[1]['tm']['kept_intervals'][0][0] += 1 / sr
            with self.assertRaisesRegex(ValueError, '不是已审子段原样PCM'):
                e.reconstruct(records, td / 'source.wav', td / 'corrupt')

    def test_low_level_protected_signal_is_not_silence_to_remove(self):
        data = {'audio': {'window': [0, 10]}}
        tm = {'protected_source_intervals': [[3., 7.]], 'audio_protection': {'source': 'actual'},
              'kept_intervals': [[0., 10.]]}
        with patch.object(e, 'audio_protection', return_value=([[3., 7.]], {'source': 'actual'})):
            self.assertEqual(e.check_protected(tm, data, 1000)['coverage'][0]['covered_samples'], 4000)
            tm['kept_intervals'] = [[0., 4.], [6., 10.]]
            with self.assertRaisesRegex(ValueError, '未逐样本保留'):
                e.check_protected(tm, data, 1000)

    def test_gain_delay_noise_and_single_second_level_rejected(self):
        sr = 8000
        rng = np.random.default_rng(91)
        x = rng.normal(0, .08, (sr * 200, 1)).astype('float32')
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            float_wav(td / 'ref.wav', x, sr)
            float_wav(td / 'same.wav', x, sr)
            self.assertTrue(e.compare_audio(td / 'ref.wav', td / 'same.wav', 0, len(x))['ok'])
            mutations = {'gain': x * 10 ** (.1 / 20), 'sample_delay': np.roll(x, 1, axis=0),
                         'noise': x + rng.normal(0, .008, x.shape).astype('float32')}
            one_second = x.copy()
            one_second[sr * 17:sr * 18] *= 10 ** (1.1 / 20)
            mutations['one_second'] = one_second
            for key, y in mutations.items():
                float_wav(td / (key + '.wav'), y, sr)
                with self.subTest(mutation=key), self.assertRaisesRegex(ValueError, '原声核验失败'):
                    e.compare_audio(td / 'ref.wav', td / (key + '.wav'), 0, len(x))

    def test_missing_2015_explicit_high_bitrate_is_rejected(self):
        records = [{'tm': {}}] * 3
        self.assertEqual(e.selected_bitrate(records, 2009), '192k')
        with self.assertRaisesRegex(ValueError, '最高明确策略'):
            e.selected_bitrate(records, 2015)
        self.assertEqual(e.selected_bitrate([{'tm': {'aac_bitrate': '256k'}}, *records[1:]], 2015), '256k')


if __name__ == '__main__':
    unittest.main(verbosity=2)
