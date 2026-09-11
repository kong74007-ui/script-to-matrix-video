"""Portable GPU policy tests; no private footage or GPU required."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import gpu_runtime as gpu

FIXTURE = '''function metadata() { return {
      videoCodec: videoStream.codec_name || "unknown",
}; }
function buildEncoderArgs(options, inputArgs, outputPath, gpuEncoder = null) {
  const shouldUseGpu = useGpu && gpuEncoder !== null;
          args.push("-preset", mapPresetForGpuEncoder("nvenc", preset2));
}
function buildStreamingArgs(options, outputPath, gpuEncoder = null) {
  const shouldUseGpu = useGpu && gpuEncoder !== null;
          args.push("-preset", mapPresetForGpuEncoder("nvenc", preset2));
}
async function extractVideoFramesRange(videoPath) {
  const args = [];
}
function end() {}
'''

class GpuRuntime(unittest.TestCase):
    def test_h264_high10_is_not_nvdec(self):
        self.assertFalse(gpu.supports_nvdec('h264', 'yuv420p10le'))
        self.assertTrue(gpu.supports_nvdec('hevc', 'yuv420p10le'))
        self.assertFalse(gpu.supports_nvdec('hevc', 'yuv422p10le'))

    def command(self):
        return ['ffmpeg', '-i', 'input.mp4', '-vf', 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30',
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-t', '8', 'output.mp4']

    @patch.object(gpu, 'video_probe', return_value={'codec_name':'h264', 'pix_fmt':'yuv420p'})
    def test_decode_scale_encode_and_timing(self, probe):
        original = self.command()
        migrated = gpu.accelerate_ffmpeg(original)
        self.assertIn('libx264', original)
        self.assertNotIn('libx264', migrated)
        self.assertNotIn('-crf', migrated)
        self.assertEqual(migrated[migrated.index('-hwaccel')+1], 'cuda')
        self.assertEqual(migrated[migrated.index('-c:v')+1], 'h264_nvenc')
        self.assertEqual(migrated[migrated.index('-t')+1], '8')
        self.assertIn('scale_cuda=1080:1920', migrated[migrated.index('-vf')+1])

    @patch.object(gpu, 'video_probe', return_value={'codec_name':'prores', 'pix_fmt':'yuv422p10le'})
    def test_unsupported_decode_keeps_gpu_encode(self, probe):
        command = gpu.accelerate_ffmpeg(self.command())
        self.assertNotIn('-hwaccel', command)
        self.assertIn('h264_nvenc', command)

    def test_audio_and_copy_are_unchanged(self):
        for cmd in (['ffmpeg','-i','a.wav','-c:a','aac','a.m4a'], ['ffmpeg','-i','in.mp4','-c:v','copy','out.mp4']):
            self.assertEqual(gpu.accelerate_ffmpeg(cmd), cmd)

    def test_preserve_tonemap_and_effects(self):
        prefix = 'zscale=t=linear,tonemap=mobius,zscale=t=bt709,'
        result = gpu.gpu_filter(prefix+'scale=1080:640:force_original_aspect_ratio=increase,crop=1080:640')
        self.assertTrue(result.startswith(prefix))
        self.assertTrue(result.endswith('crop=1080:640'))
        self.assertEqual(gpu.gpu_filter('scale=iw/2:ih/2,eq=contrast=1.05'), 'scale=iw/2:ih/2,eq=contrast=1.05')

    def test_patch_blocks_both_cpu_encode_paths(self):
        value = gpu.patch_gpu_source(FIXTURE)
        self.assertEqual(value.count('CPU encoding refused'), 2)
        self.assertIn('"-hwaccel", "cuda"', value)
        self.assertIn('includes(metadata.gpuPixelFormat)', value)
        with self.assertRaises(ValueError):
            gpu.patch_gpu_source(FIXTURE.replace('  const shouldUseGpu = useGpu && gpuEncoder !== null;', 'changed'))

    def test_temporary_cli_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'dist').mkdir()
            (root/'package.json').write_text(json.dumps({'version':'0.8.34'}))
            original = root/'dist/cli.js'
            original.write_text(FIXTURE)
            with gpu.gpu_cli(original) as value:
                temporary = Path(value)
                self.assertTrue(temporary.exists())
            self.assertEqual(original.read_text(), FIXTURE)
            self.assertFalse(temporary.exists())

    def test_template_entrypoints_and_portable_copies(self):
        root = Path(__file__).resolve().parents[1]
        canonical = (root/'scripts/gpu_runtime.py').read_bytes()
        folders = list((root/'assets/templates').glob('*/package.json'))
        self.assertEqual(len(folders), 9)
        for package in folders:
            data = json.loads(package.read_text(encoding='utf-8'))
            command = data['scripts']['render']
            self.assertTrue('gpu_runtime.py' in command or 'render_gpu_hdr.py' in command, package)
            self.assertEqual((package.parent/'gpu_runtime.py').read_bytes(), canonical, package)

    @patch.object(gpu, 'video_probe')
    def test_actual_encoder_not_just_requested_flag(self, probe):
        probe.return_value = {'codec_name':'h264', 'tags':{'encoder':'Lavc libx264'}}
        with self.assertRaises(ValueError):
            gpu.verify_nvenc('file.mp4')
        probe.return_value['tags']['encoder'] = 'Lavc h264_nvenc'
        self.assertEqual(gpu.verify_nvenc('file.mp4')['codec_name'], 'h264')

if __name__ == '__main__':
    unittest.main()
