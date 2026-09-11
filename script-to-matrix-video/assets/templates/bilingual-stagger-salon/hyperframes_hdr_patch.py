"""Narrow, temporary HyperFrames 0.8.38 HDR/NVENC bridge; never edit installed CLI."""
from contextlib import contextmanager
from pathlib import Path
import tempfile
from gpu_runtime import patch_gpu_source


def patch_source(source):
    start = source.index('async function runCaptureHdrStage(input2) {')
    anchor = '        hdr: preset2.hdr,\n        rawInputFormat: "rgb48le"'
    index = source.index(anchor, start)
    if index - start > 12000:
        raise ValueError('Unexpected HDR stage layout; re-audit the CLI')
    source = source[:index] + source[index:].replace(anchor,
        '        hdr: preset2.hdr,\n        useGpu: job.config.useGpu,\n        rawInputFormat: "rgb48le"', 1)
    start = source.index('function buildStreamingArgs(options, outputPath, gpuEncoder = null) {')
    index = source.index('  const shouldUseGpu = useGpu && gpuEncoder !== null;', start)
    guard = '''  if (options.rawInputFormat && options.hdr && useGpu && gpuEncoder !== "nvenc") {
    throw new Error("Verified HDR profile requires NVENC; CPU fallback refused");
  }
'''
    source = source[:index] + guard + source[index:]
    anchor = '          args.push("-preset", mapPresetForGpuEncoder("nvenc", preset2));'
    index = source.index(anchor, start)
    extra = '''
          if (options.rawInputFormat && options.hdr && codec === "h265") {
            args.push("-profile:v", "main10", "-tune", "hq", "-rc", "vbr", "-tag:v", "hvc1");
            if (!bitrate) args.push("-b:v", "0");
          }'''
    return source[:index] + source[index:].replace(anchor, anchor + extra, 1)


@contextmanager
def patched_cli(cli):
    cli = Path(cli)
    content = patch_gpu_source(patch_source(cli.read_text(encoding='utf-8')))
    # Keep relative imports/runtime assets resolving to the installed package.
    # Unique per invocation; the original CLI and other tasks are untouched.
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.mjs',
                                     prefix='.codex-hdr-', dir=cli.parent, delete=False) as f:
        f.write(content)
        temporary = Path(f.name)
    try:
        yield str(temporary)
    finally:
        temporary.unlink(missing_ok=True)
