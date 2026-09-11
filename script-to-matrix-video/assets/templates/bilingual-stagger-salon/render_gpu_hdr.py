"""Verified NVENC encoding + native HDR composition. No CPU-encoder/SDR fallback."""
import argparse
from fractions import Fraction
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from hyperframes_hdr_patch import patched_cli

HIDDEN = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def run(command, **kwargs):
    return subprocess.run(command, creationflags=HIDDEN, check=True, **kwargs)


def probe(path, binary):
    return json.loads(run([binary, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
                          capture_output=True, text=True, encoding='utf-8').stdout)


class Composition(HTMLParser):
    def __init__(self):
        super().__init__()
        self.videos = []
        self.fps = 30
        self.duration = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'video' and a.get('src'):
            self.videos.append(a['src'])
        if a.get('data-composition-id'):
            self.fps = float(a.get('data-fps', 30))
            self.duration = float(a['data-duration'])


def is_hdr(stream):
    return (stream.get('color_transfer') in ('arib-std-b67', 'smpte2084')
            and stream.get('color_primaries') == 'bt2020'
            and any(bit in stream.get('pix_fmt', '') for bit in ('10', '12', '16')))


def verify_output(info, doc):
    stream = next(s for s in info['streams'] if s['codec_type'] == 'video')
    valid = (stream.get('codec_name') == 'hevc' and stream.get('profile') == 'Main 10'
             and stream.get('pix_fmt') == 'yuv420p10le' and is_hdr(stream)
             and stream.get('color_space') == 'bt2020nc'
             and 'hevc_nvenc' in stream.get('tags', {}).get('encoder', ''))
    if not valid:
        raise RuntimeError('Output fails HEVC Main10 HDR/NVENC contract')
    if abs(float(info['format']['duration'])-doc.duration) > .1:
        raise RuntimeError('Output duration mismatch')
    if float(Fraction(stream.get('avg_frame_rate', '0'))) != doc.fps:
        raise RuntimeError('Output frame rate mismatch')
    if stream.get('width') != 1080 or stream.get('height') != 1920:
        raise RuntimeError('Output canvas mismatch')
    if not any(s.get('codec_type') == 'audio' and s.get('codec_name') == 'aac' for s in info['streams']):
        raise RuntimeError('Narration/AAC output missing')
    return stream


def resolve_runtime(args):
    config_file = Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))/'script-to-matrix-video/render-runtime.json'
    config = json.loads(config_file.read_text(encoding='utf-8-sig')) if config_file.exists() else {}
    directory = args.ffmpeg_bin or config.get('ffmpeg_bin')
    suffix = '.exe' if os.name == 'nt' else ''
    ffmpeg = str(Path(directory)/('ffmpeg'+suffix)) if directory else shutil.which('ffmpeg')
    ffprobe = str(Path(directory)/('ffprobe'+suffix)) if directory else shutil.which('ffprobe')
    cli = args.cli or config.get('hyperframes_cli')
    node = shutil.which('node')
    if not cli or not Path(cli).is_file() or not node:
        raise ValueError('Provide --cli path/to/hyperframes/dist/cli.js (0.8.38); install with npx hyperframes@0.8.38 --version first')
    package = json.loads((Path(cli).parents[1]/'package.json').read_text(encoding='utf-8'))
    if package.get('name') != 'hyperframes' or package.get('version') != '0.8.38':
        raise ValueError('Use verified HyperFrames 0.8.38 for this profile; validate upgrades separately')
    if not ffmpeg or not ffprobe or not Path(ffmpeg).is_file() or not Path(ffprobe).is_file():
        raise ValueError('FFmpeg/ffprobe not found')
    return node, str(Path(cli).resolve()), ffmpeg, ffprobe


def main(args):
    project = Path(args.project).resolve()
    output = Path(args.output)
    output = output.resolve() if output.is_absolute() else (project/output).resolve()
    if output.exists():
        raise ValueError('Output exists; choose a new filename')
    if output.suffix.lower() != '.mp4':
        raise ValueError('HDR output must be MP4')
    node, cli, ffmpeg, ffprobe = resolve_runtime(args)
    doc = Composition()
    doc.feed((project/'index.html').read_text(encoding='utf-8'))
    sources = []
    for src in doc.videos:
        if '://' in src:
            raise ValueError('Copy original source files locally before rendering')
        info = probe(project/src, ffprobe)
        stream = next(s for s in info['streams'] if s['codec_type'] == 'video')
        sources.append({'src':src, 'hdr':is_hdr(stream), 'codec':stream.get('codec_name'),
                        'pixel_format':stream.get('pix_fmt'), 'transfer':stream.get('color_transfer')})
    if not sources or not any(s['hdr'] for s in sources):
        raise ValueError('No genuine 10-bit HDR video: replace SDR proxies with original HDR sources first')
    # Test the actual HEVC Main10 hardware path, not just compiled encoder availability.
    run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', 'color=black:s=256x256:r=30:d=0.1',
         '-vf', 'format=p010le', '-c:v', 'hevc_nvenc', '-profile:v', 'main10',
         '-preset', 'p7', '-tune', 'hq', '-rc', 'vbr', '-cq', '16', '-b:v', '0', '-f', 'null', '-'])
    if args.preflight_only:
        print(json.dumps({'nvenc_main10':True,'sources':sources,'fps':doc.fps}, ensure_ascii=False))
        return
    env = dict(os.environ, HYPERFRAMES_FFMPEG_PATH=ffmpeg, HYPERFRAMES_FFPROBE_PATH=ffprobe)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [node, cli, 'render', str(project), '--gpu',
               '--no-browser-gpu' if args.no_browser_gpu else '--browser-gpu', '--hdr',
               '--quality', 'delivery', '--crf', str(args.crf), '--video-frame-format', 'png',
               '--fps', str(int(doc.fps)), '--workers', str(args.workers), '--strict', '--output', str(output)]
    log = output.with_suffix('.render.log')
    with patched_cli(cli) as runtime_cli, log.open('w', encoding='utf-8') as sink:
        command[1] = runtime_cli
        process = subprocess.Popen(command, env=env, cwd=project, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                                   creationflags=HIDDEN)
        for line in process.stdout:
            sink.write(line)
            sink.flush()
            print(line.rstrip(), flush=True)
        if process.wait() != 0:
            raise RuntimeError('HyperFrames render failed; inspect private render log')
    info = probe(output, ffprobe)
    stream = verify_output(info, doc)
    report = {'verified':True, 'output':str(output), 'sources':sources, 'video':stream,
              'runtime_patch':'0.8.38 HDR useGpu forwarding; original CLI unchanged',
              'note':'HDR HLG/PQ basic signal; not a promise of Dolby Vision RPU or HDR10 static mastering metadata; not lossless'}
    output.with_suffix('.verified.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('VERIFIED: HEVC Main10 / BT.2020 HDR / NVENC')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', nargs='?', default='.')
    parser.add_argument('--output', default='renders/final-gpu-hdr.mp4')
    parser.add_argument('--ffmpeg-bin')
    parser.add_argument('--cli')
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--browser-gpu', action='store_true',
                        help='Browser GPU is now the default; retained for compatibility')
    parser.add_argument('--no-browser-gpu', action='store_true',
                        help='Explicit diagnostic override; NVENC encoding stays mandatory')
    parser.add_argument('--crf', type=int, default=16, choices=range(0,52))
    parser.add_argument('--preflight-only', action='store_true')
    try:
        main(parser.parse_args())
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
