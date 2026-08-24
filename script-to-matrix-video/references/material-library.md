# Material library integration

Use this reference when a local or SSH-accessible Huangque-style material
library is available. The library is optional; the video project must remain
self-contained after selected files are copied into it.

## Selection order

1. Use assets explicitly supplied or required by the client.
2. Search the configured library and consider only records whose `状态` is
   `可使用`.
3. Visually inspect the best metadata matches and copy only the assets that
   actually support the current scene.
4. In Function 1 (`script-video`) only, generate an AI image when no usable
   supplied or library asset covers the scene.

Function 2 (`text-media-text`) is library-only after supplied assets. AI image
or video generation is prohibited. If no contextually suitable `可使用` record
exists, mark the affected output `material_missing`, report the searches tried,
and continue other batch jobs. Do not substitute unrelated filler.

Do not treat keyword similarity as final approval. Reject a candidate when its
subject, location, demographic, action, embedded wording, quality, or visual
tone conflicts with the full copy. Avoid repeated filler shots. One strong
asset is preferable to three vaguely related assets.

## Library contract

The library root must contain `index.jsonl`. Each record should provide:

- `record_id`
- `素材名称`
- `素材类型`: `图片`, `视频`, or `BGM`
- `状态`
- `server_relative_path`
- useful semantic fields such as `标签`, `一级场景`, `二级场景`, `使用环节`,
  `情绪氛围`, `画面方向`, `宽度`, `高度`, and `时长秒`

The current workflow uses `状态 == 可使用` as the availability gate. It does
not silently rewrite library metadata.

## Inspect and search

The helper resolves connection settings in this order: command-line arguments,
`MATRIX_MATERIAL_LIBRARY_*` environment variables, then the per-user profile at
`~/.codex/script-to-matrix-video/material-library.json`. The profile contains
only non-secret routing settings:

```json
{
  "host": "material-library-ssh-alias",
  "user": "media-reader",
  "remote_root": "/srv/huangque-media"
}
```

Configure the SSH alias and identity in `~/.ssh/config`. Never put a password
or private-key content in the JSON profile.

Local library:

```powershell
python scripts/material_library.py inspect --root "D:\media\huangque-media"
python scripts/material_library.py search --root "D:\media\huangque-media" --query "私域 社群 女性 商务" --type 视频 --orientation 竖屏
```

Remote library over SSH:

```powershell
python scripts/material_library.py search --host media.example.com --user media-reader --remote-root /srv/huangque-media --query "数据 商务 增长" --type 视频 --orientation 竖屏
```

Use space-separated semantic keywords rather than pasting the whole script.
Search separately for each scene function: hook, comparison, proof, process,
emotion, or CTA.

## Copy selected assets into the project

```powershell
python scripts/material_library.py fetch --host media.example.com --user media-reader --remote-root /srv/huangque-media --record-id RECORD_ID --destination "D:\video-project\assets\library"
```

Remote mode uses the computer's existing SSH key or SSH agent. The helper has
no password argument and must never be modified to put a password in a command,
manifest, log, or distributable Skill. A read-only material-library account is
preferred.

Record the copied local path and source metadata in `project.json`. The renderer
accepts copied images and videos through each scene's `media` array. Never point
a distributable project at a remote library path that the recipient cannot
access.

## BGM choice

Search `素材类型=BGM` using the video's content and emotional arc. Prefer:

- community, private-domain, women, social connection: light social rhythm;
- data, business, growth, execution: steady or progressive business rhythm;
- adversity, persistence, warning: restrained motivational rhythm;
- future, opportunity, positive CTA: hopeful and light rhythm.

Preview the track. Avoid vocals that compete with narration and avoid dramatic
music that overstates ordinary knowledge content. Copy the chosen file into
`assets/bgm`, record it under top-level `bgm`, and let the renderer handle the
loop, fades, loudness, and optional ducking.
