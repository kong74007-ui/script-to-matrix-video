# Installation and first run

Read this reference only when installing the Skill on a new machine or diagnosing missing dependencies.

## Install the Skill

Copy the complete `script-to-matrix-video` folder to the user's Codex skills directory:

- Windows: `%USERPROFILE%\.codex\skills\script-to-matrix-video`
- macOS/Linux: `~/.codex/skills/script-to-matrix-video`

Keep `SKILL.md`, `agents`, `references`, `scripts`, and `requirements.txt` together. Restart Codex after installing so the Skill is rediscovered.

Keep `assets/templates` and `assets/fonts` as well. The 13-style catalog and four licensed Chinese font families are part of the runtime, so no separate operating-system font installation is required for bundled templates.

The Windows installer runs the source environment check and catalog regression suite, then validates every bundled font SHA-256 before it backs up or replaces an existing Skill. A missing, malformed, or altered runtime asset must stop installation.

## Runtime dependencies

Rendering requires:

- Python 3.10 or newer.
- FFmpeg with both `ffmpeg` and `ffprobe` available on `PATH`.
- Node.js with npm is required only for the 18 `ref-` HyperFrames typography templates; the wrapper pins HyperFrames `0.8.16`.
- An image-generation capability in the running Codex environment, or user-supplied local images.

Material-library access is required on the first installation. Connect either a
local/mounted library root or OpenSSH (`ssh`) plus an already configured SSH
key/agent. Passwords are not accepted by the helper and must not be added to
this Skill.

Alibaba narration additionally requires:

```powershell
python -m pip install -r "$env:USERPROFILE\.codex\skills\script-to-matrix-video\requirements.txt"
```

On macOS or Linux, use `python3` and the corresponding `~/.codex/skills/...` path.

Configure `DASHSCOPE_API_KEY` as a user or process environment variable. Do not paste it into `project.json`, source code, chat output, or the Skill archive. Restart Codex after changing a persistent environment variable.

No-narration videos do not require DashScope or an Alibaba API key.

## Connect the required material library

Every new machine must connect and validate its own library before installation
can complete or a video can render. The connection profile is per-user and is
not bundled with the Skill.

Connect a local or mounted root and save the verified profile:

```powershell
python scripts/material_library.py connect --root "D:\media\huangque-media"
```

Or connect remote read access without storing a password:

```powershell
python scripts/material_library.py connect --host material-library-ssh-alias --user media-reader --remote-root "/srv/huangque-media"
```

The `connect` command validates `index.jsonl` first, then writes the persistent
per-user profile to `~/.codex/script-to-matrix-video/material-library.json`:

```json
{
  "host": "material-library-ssh-alias",
  "user": "media-reader",
  "remote_root": "/srv/huangque-media"
}
```

Put the host name and `IdentityFile` in `~/.ssh/config`. The JSON profile must
never contain a password or private key. Environment variables remain supported
for managed deployments, but they must still pass the same inspection gate.

Verify it with:

```powershell
python scripts/material_library.py inspect
```

If this command fails, first-time setup is incomplete. Do not start a render or
fall back to generated media; correct the local path, SSH authorization, remote
root, or library index and run it again.

Prefer a read-only server account. Copy every selected file into the task-owned
project before rendering so the final project is portable and reproducible.

## Verify the machine

For no-narration videos:

```powershell
python scripts/check_environment.py
```

For Alibaba narration:

```powershell
python scripts/check_environment.py --require-tts
```

Run the command from the installed Skill folder. The checker reports only whether the API key exists; it never prints the key.

## Invoke the Skill

Example with narration:

```text
使用 $script-to-matrix-video，把下面的客户文案制作成9:16知识口播视频，使用阿里配音，直接输出成片：……
```

Example without narration using the structured layout:

```text
使用 $script-to-matrix-video 的模板成片功能，无配音。采用上方标题、中间素材库图片或视频、下方固定副标题；禁止AI生成素材，直接输出成片：……
```

Generated project folders and media must stay outside the installed Skill directory.

## Common setup failures

- `ffmpeg is required`: install FFmpeg and reopen the terminal or Codex so `PATH` refreshes.
- `No module named dashscope`: install `requirements.txt` with the same Python executable used to run the Skill.
- `DASHSCOPE_API_KEY is not configured`: configure the environment variable, or set `voice.enabled` to `false` for a no-narration video.
- Function 1 images cannot be generated: enable image generation in the Codex environment or provide local image files for every scene. Function 2 must use supplied/library media and must not generate replacements.
- `ssh is required`: install/enable OpenSSH, or mount/copy the library locally and set `MATRIX_MATERIAL_LIBRARY_ROOT`.
- `Set --root, configure SSH host...`: run `material_library.py connect` with the new machine's local root or SSH connection before installing or rendering.
- `Material status is ...`: only `可使用` records are eligible by default; update the source library through its approved review process rather than bypassing the filter.
- BGM is enabled but skipped: copy a selected track into the project and set `bgm.path`, or disable BGM explicitly.
- `fonts_dir is not a directory`: reinstall the complete Skill, or point `render.fonts_dir` at a custom font directory inside the current project. Do not use a machine-specific external path in a portable project.
