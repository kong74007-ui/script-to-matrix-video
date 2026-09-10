"""Offline input-contract regression tests; no private media needed."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import prepare_bilingual_stagger as prep


class TemplateContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        for i, name in enumerate(('voice.mp3', 'a.mp4', 'b.mp4', 'c.mp4')):
            (self.base/name).write_bytes(bytes([i]))
        self.task = {
            'voice': 'voice.mp3',
            'media': [{'path': n, 'source_type': 'client'} for n in ('a.mp4','b.mp4','c.mp4')],
            'titles': [{'text': '一起交流', 'start': 0, 'end': 'end'}],
            'cues': [{'text': '一起交流', 'en': "Let us connect", 'times': [0,.3,.6,.9],
                      'end': 'end', 'row': 0, 'yellow': [2,3]}]}
        def probe(path):
            if path.suffix == '.mp3':
                return {'streams': [{'codec_type': 'audio'}], 'format': {'duration': '20.5'}}
            return {'streams': [{'codec_type': 'video', 'codec_name': 'h264',
                    'color_transfer': 'bt709', 'color_space': 'bt709',
                    'width': 720, 'height': 1280}], 'format': {'duration': '15'}}
        mock = patch.object(prep, 'probe', side_effect=probe)
        mock.start()
        self.addCleanup(mock.stop)

    def reject(self, edit):
        task = copy.deepcopy(self.task)
        edit(task)
        with self.assertRaises(ValueError):
            prep.validate(task, self.base)

    def test_duration_follows_voice(self):
        self.assertAlmostEqual(prep.validate(self.task, self.base)[2], 21.1)

    def test_reject_truncation(self):
        self.reject(lambda t: t.update(duration=8))

    def test_reject_bgm(self):
        self.reject(lambda t: t.update(bgm='music.mp3'))

    def test_reject_duplicate(self):
        self.reject(lambda t: t['media'][1].update(path='a.mp4'))

    def test_reject_ai(self):
        self.reject(lambda t: t['media'][0].update(source_type='ai'))

    def test_reject_unapproved_library(self):
        self.reject(lambda t: t['media'][0].update(source_type='library'))

    def test_reject_caption_times(self):
        self.reject(lambda t: t['cues'][0].update(times=[0,.3]))

    def test_reject_gap(self):
        self.reject(lambda t: t['media'][1].update(start=8))

    def test_reject_nonfinite(self):
        self.reject(lambda t: t.update(duration=float('nan')))


if __name__ == '__main__':
    unittest.main()
