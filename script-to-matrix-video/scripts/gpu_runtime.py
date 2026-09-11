"""Shared NVIDIA runtime for saved templates. GPU encoding is mandatory, not a hint.

Portable copies in template folders are synchronized by sync_gpu_runtime.py.
No installed HyperFrames files are modified. CPU-only filters/audio stay intact.
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

SUPPORTED = ('0.8.29', '0.8.33', '0.8.34', '0.8.38')
FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
DECODE_CODECS = ('h264', 'hevc', 'vp9', 'av1', 'mpeg2video')


def supports_nvdec(codec, pixel_format):
    if codec not in DECODE_CODECS:
        return False
    formats = ('yuv420p', 'nv12') if codec in ('h264', 'mpeg2video') else ('yuv420p', 'nv12', 'yuv420p10le', 'p010le')
    return pixel_format in formats


def run(args, **kwargs):
    return subprocess.run(args, check=True, creationflags=FLAGS, **kwargs)


def video_probe(path, ffprobe='ffprobe'):
    data = json.loads(run([ffprobe, '-v', 'error', '-select_streams', 'v:0',
                           '-show_streams', '-of', 'json', str(path)],
                          capture_output=True, text=True, encoding='utf-8').stdout)
    return data['streams'][0]


def nvenc_preflight(ffmpeg='ffmpeg', hevc=False):
    run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', 'color=s=256x256:r=30:d=0.1',
         '-vf', 'format=p010le' if hevc else 'format=yuv420p', '-c:v',
         'hevc_nvenc' if hevc else 'h264_nvenc', '-preset', 'p5', '-rc', 'vbr',
         '-cq', '16', '-b:v', '0', '-f', 'null', '-'], capture_output=True)


def gpu_filter(value):
    # Only migrate the known SDR scaling stage. Preserve tone mapping and crop math.
    return re.sub(r'(?<![\w_])scale=(\d+):(\d+):force_original_aspect_ratio=increase',
        lambda m: ('format=yuv420p,hwupload_cuda,scale_cuda=' + m[1] + ':' + m[2] +
                   ':force_original_aspect_ratio=increase:force_divisible_by=2:interp_algo=bicubic,'
                   'hwdownload,format=yuv420p'), value)


def accelerate_ffmpeg(command):
    """Migrate one existing SDR preparation/trim command without changing audio/timing.

    NVDEC downloads frames for existing CPU filters/autorotation; numeric SDR resize
    runs on CUDA. Unsupported source codecs decode in software, explicitly logged.
    Failures do not retry with a CPU encoder or leave a success report.
    """
    args = list(command)
    if '-c:v' not in args or args[args.index('-c:v') + 1] != 'libx264':
        return args
    args[args.index('-c:v') + 1] = 'h264_nvenc'
    if '-preset' in args:
        args[args.index('-preset') + 1] = 'p5'
    if '-crf' in args:
        i = args.index('-crf')
        args[i:i+2] = ['-cq', '16']
    args[-1:-1] = ['-rc', 'vbr', '-b:v', '0', '-tune', 'hq']
    if '-vf' in args:
        i = args.index('-vf') + 1
        args[i] = gpu_filter(args[i])
    if '-i' in args:
        i = args.index('-i')
        ffprobe = str(Path(args[0]).with_name('ffprobe.exe' if os.name == 'nt' else 'ffprobe'))
        info = video_probe(args[i+1], ffprobe)
        if supports_nvdec(info.get('codec_name'), info.get('pix_fmt')):
            args[i:i] = ['-hwaccel', 'cuda']
        else:
            print('[GPU] Source codec/pixel format requires CPU decode; encoding remains NVENC.', file=sys.stderr)
    return args


def patch_gpu_source(source):
    """Audited narrow bridges shared by the four saved CLI pins."""
    metadata_anchor = '      videoCodec: videoStream.codec_name || "unknown",'
    if source.count(metadata_anchor) != 1:
        raise ValueError('Video metadata bridge changed; re-audit pixel-format detection')
    source = source.replace(metadata_anchor, metadata_anchor + '\n      gpuPixelFormat: videoStream.pix_fmt || "",')
    for name in ('buildEncoderArgs', 'buildStreamingArgs'):
        start = source.index('function ' + name + '(')
        end = source.index('\nfunction ', start + 10)
        block = source[start:end]
        anchor = '  const shouldUseGpu = useGpu && gpuEncoder !== null;'
        if block.count(anchor) != 1:
            raise ValueError('GPU encoder bridge changed; re-audit ' + name)
        block = block.replace(anchor, '  if (!useGpu || gpuEncoder !== "nvenc") throw new Error("Template requires NVIDIA NVENC; CPU encoding refused");\n' + anchor)
        preset = '          args.push("-preset", mapPresetForGpuEncoder("nvenc", preset2));'
        if block.count(preset) != 1:
            raise ValueError('NVENC rate control bridge changed')
        block = block.replace(preset, preset + '\n          args.push("-rc", "vbr", "-tune", "hq");\n          if (!bitrate) args.push("-b:v", "0");')
        source = source[:start] + block + source[end:]
    start = source.index('async function extractVideoFramesRange(')
    end = source.index('\nfunction ', start)
    block = source[start:end]
    anchor = '  const args = [];'
    if block.count(anchor) != 1:
        raise ValueError('Video extraction bridge changed')
    block = block.replace(anchor, anchor + '''
  if ((metadata.videoCodec === "h264" && ["yuv420p", "nv12"].includes(metadata.gpuPixelFormat)) || (["hevc", "h265"].includes(metadata.videoCodec) && ["yuv420p", "yuv420p10le", "nv12", "p010le"].includes(metadata.gpuPixelFormat))) {
    args.push("-hwaccel", "cuda");
  }
''', 1)
    source = source[:start] + block + source[end:]
    # Native HDR extraction is a separate path. Keep high-bit-depth CPU color math.
    anchor = '      const ffmpegArgs = [];\n      if (window3.finalFrameOnly) {'
    if anchor in source:
        source = source.replace(anchor, '''      const ffmpegArgs = [];
      const gpuSourceMetadata = await extractMediaMetadataImpl(srcPath);
      if ((gpuSourceMetadata.videoCodec === "h264" && ["yuv420p", "nv12"].includes(gpuSourceMetadata.gpuPixelFormat)) || (["hevc", "h265"].includes(gpuSourceMetadata.videoCodec) && ["yuv420p", "yuv420p10le", "nv12", "p010le"].includes(gpuSourceMetadata.gpuPixelFormat))) ffmpegArgs.push("-hwaccel", "cuda");
      if (window3.finalFrameOnly) {''', 1)
    return source


@contextmanager
def gpu_cli(cli):
    path = Path(cli)
    version = json.loads((path.parents[1]/'package.json').read_text(encoding='utf-8'))['version']
    if version not in SUPPORTED:
        raise ValueError('Unaudited HyperFrames version: ' + version)
    content = patch_gpu_source(path.read_text(encoding='utf-8'))
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.mjs',
                                     prefix='.codex-template-gpu-', dir=path.parent, delete=False) as f:
        f.write(content)
        temporary = Path(f.name)
    try:
        yield str(temporary)
    finally:
        temporary.unlink(missing_ok=True)


def resolve_cli(version):
    if version not in SUPPORTED:
        raise ValueError('Unsupported CLI pin: ' + version)
    config_path = Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))/'script-to-matrix-video/render-runtime.json'
    config = json.loads(config_path.read_text(encoding='utf-8-sig')) if config_path.exists() else {}
    npm = shutil.which('npm')
    if not npm:
        raise ValueError('Install Node.js/npm first')
    cache = Path(run([npm, 'config', 'get', 'cache'], capture_output=True, text=True).stdout.strip())
    candidates = [Path.cwd()/'node_modules/hyperframes/dist/cli.js']
    if config.get('hyperframes_cli'):
        candidates.insert(0, Path(config['hyperframes_cli']))
    candidates.extend(cache.glob('_npx/*/node_modules/hyperframes/dist/cli.js'))
    for path in candidates:
        package = path.parents[1]/'package.json'
        if path.is_file() and package.is_file() and json.loads(package.read_text(encoding='utf-8')).get('version') == version:
            return path, config
    raise ValueError('Install the pinned runtime first: npx --yes hyperframes@' + version + ' --version')


def verify_nvenc(path, ffprobe='ffprobe'):
    info = video_probe(path, ffprobe)
    if info.get('codec_name') not in ('h264', 'hevc') or 'nvenc' not in info.get('tags', {}).get('encoder', ''):
        raise ValueError('Output is not verified NVENC: ' + str(path))
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True, choices=SUPPORTED)
    parser.add_argument('options', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    options = args.options[1:] if args.options[:1] == ['--'] else args.options
    if '--hdr' in options:
        raise ValueError('Native HDR uses render_gpu_hdr.py, not the SDR template wrapper')
    if '--output' not in options and '-o' not in options:
        options += ['--output', 'renders/gpu-' + uuid.uuid4().hex[:12] + '.mp4']
    key = '--output' if '--output' in options else '-o'
    output_pattern = options[options.index(key)+1]
    import glob
    matching = re.sub(r'\{[^}]+\}', '*', output_pattern)
    if glob.glob(matching):
        raise ValueError('Output exists; choose a new filename or empty batch output directory')
    cli, config = resolve_cli(args.version)
    directory = config.get('ffmpeg_bin')
    suffix = '.exe' if os.name == 'nt' else ''
    ffmpeg = str(Path(directory)/('ffmpeg'+suffix)) if directory else shutil.which('ffmpeg')
    ffprobe = str(Path(directory)/('ffprobe'+suffix)) if directory else shutil.which('ffprobe')
    nvenc_preflight(ffmpeg)
    if '--no-browser-gpu' not in options and '--browser-gpu' not in options:
        options.append('--browser-gpu')
    if '--gpu' not in options:
        options.append('--gpu')
    if '--sdr' not in options:
        options.append('--sdr')
    if '--strict' not in options:
        options.append('--strict')
    if '--crf' not in options and '--video-bitrate' not in options:
        options += ['--crf', '16']
    env = dict(os.environ, HYPERFRAMES_FFMPEG_PATH=ffmpeg, HYPERFRAMES_FFPROBE_PATH=ffprobe)
    with gpu_cli(cli) as patched:
        command = [shutil.which('node'), patched, 'render', *options]
        process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                                   errors='replace', creationflags=FLAGS)
        for line in process.stdout:
            print(line.rstrip(), flush=True)
        if process.wait() != 0:
            raise subprocess.CalledProcessError(process.returncode, command)
    # Explicit output paths (including batch patterns) are the public entry contract.
    if '--output' in options or '-o' in options:
        key = '--output' if '--output' in options else '-o'
        pattern = options[options.index(key)+1]
        files = glob.glob(re.sub(r'\{[^}]+\}', '*', pattern))
        if not files:
            raise ValueError('Render created no output matching requested path')
        for path in files:
            verify_nvenc(path, ffprobe)
        print('[GPU] Verified NVENC outputs:', len(files))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
