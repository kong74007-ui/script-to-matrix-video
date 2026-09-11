"""Regression tests for the isolated upstream GPU-flag bridge."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from hyperframes_hdr_patch import patch_source, patched_cli
from render_gpu_hdr import is_hdr, Composition, verify_output

FIXTURE = '''async function runCaptureHdrStage(input2) {
    hdrEncoder = await spawnStreamingEncoder(videoOnlyPath, {
        hdr: preset2.hdr,
        rawInputFormat: "rgb48le"
    });
}
function buildStreamingArgs(options, outputPath, gpuEncoder = null) {
  const shouldUseGpu = useGpu && gpuEncoder !== null;
          args.push("-preset", mapPresetForGpuEncoder("nvenc", preset2));
}
'''


class HdrBridge(unittest.TestCase):
    def test_passes_gpu_to_hdr_encoder_and_blocks_fallback(self):
        patched = patch_source(FIXTURE)
        self.assertIn('useGpu: job.config.useGpu', patched)
        self.assertIn('CPU fallback refused', patched)
        self.assertIn('"-profile:v", "main10"', patched)
        self.assertIn('"-b:v", "0"', patched)

    def test_changed_runtime_fails_closed(self):
        with self.assertRaises(ValueError):
            patch_source(FIXTURE.replace('rawInputFormat: "rgb48le"', 'rawInputFormat: "different"'))

    def test_original_unmodified_and_temp_removed_on_error(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory)/'cli.js'
            original.write_text(FIXTURE, encoding='utf-8')
            with patch('hyperframes_hdr_patch.patch_gpu_source', side_effect=lambda value: value), self.assertRaises(RuntimeError):
                with patched_cli(original) as name:
                    temp = Path(name)
                    self.assertEqual(temp.parent, original.parent)
                    self.assertNotEqual(temp.read_text(), FIXTURE)
                    raise RuntimeError('simulated render failure')
            self.assertEqual(original.read_text(), FIXTURE)
            self.assertFalse(temp.exists())

    def test_real_hdr_requires_high_bit_depth_and_bt2020(self):
        good = dict(color_transfer='arib-std-b67', color_primaries='bt2020', pix_fmt='yuv420p10le')
        self.assertTrue(is_hdr(good))
        self.assertFalse(is_hdr(dict(good, pix_fmt='yuv420p')))
        self.assertFalse(is_hdr(dict(good, color_primaries='bt709')))

    def test_composition_reads_authored_fps(self):
        composition = Composition()
        composition.feed('<main data-composition-id="main" data-fps="60" data-duration="21.1"><video src="original.mov"></video></main>')
        self.assertEqual(composition.fps, 60)
        self.assertEqual(composition.videos, ['original.mov'])

    def test_output_rejects_cpu_sdr_wrong_size_and_missing_audio(self):
        import copy
        doc = Composition()
        doc.duration, doc.fps = 21.1, 60
        video = dict(codec_type='video', codec_name='hevc', profile='Main 10',
                     pix_fmt='yuv420p10le', color_space='bt2020nc', color_primaries='bt2020',
                     color_transfer='arib-std-b67', tags={'encoder':'Lavc hevc_nvenc'},
                     width=1080, height=1920, avg_frame_rate='60/1')
        good = {'streams':[video, {'codec_type':'audio','codec_name':'aac'}],
                'format':{'duration':'21.1'}}
        self.assertEqual(verify_output(good, doc), video)
        for update in ({'tags':{'encoder':'Lavc libx265'}}, {'pix_fmt':'yuv420p'},
                       {'color_transfer':'bt709'}, {'width':720}, {'avg_frame_rate':'30/1'}):
            bad = copy.deepcopy(good)
            bad['streams'][0].update(update)
            with self.assertRaises(RuntimeError):
                verify_output(bad, doc)
        with self.assertRaises(RuntimeError):
            verify_output(dict(good, streams=[video]), doc)


if __name__ == '__main__':
    unittest.main()
