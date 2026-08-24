# Project manifest schema

Create one `project.json` for each video. Paths are relative to the manifest unless explicitly absolute.

```json
{
  "version": 1,
  "project_id": "client-topic-001",
  "source_text": "客户原始文案，逐字保留",
  "platforms": ["douyin", "xiaohongshu", "wechat_channels"],
  "canvas": {"width": 1080, "height": 1920, "fps": 30},
  "material_library": {
    "enabled": true,
    "index_source": "ssh-or-local-library",
    "required_status": "可使用",
    "selection_policy": "client-then-library-then-ai"
  },
  "layout": {
    "preset": "full-frame"
  },
  "style": {
    "preset": "native-feed-problem-solution",
    "audience": "目标受众",
    "tone": "direct-warm",
    "palette": ["#171717", "#F7F3EA", "#FF6B35"],
    "visual_bible": "全片人物、场景、光线、镜头和质感的一致性描述",
    "caption_style": "bold-clean",
    "motion_intensity": "light"
  },
  "voice": {
    "enabled": true,
    "provider": "alibaba-cloud-bailian",
    "model": "cosyvoice-v3-flash",
    "voice": "longxiaoxia_v3",
    "speech_rate": 1.0,
    "volume": 50,
    "tail_padding": 0.2,
    "normalize": true
  },
  "bgm": {
    "enabled": "auto",
    "path": "assets/bgm/selected-track.mp3",
    "record_id": "library-record-id",
    "title": "选中的曲目名",
    "loop_mode": "crossfade",
    "crossfade_seconds": 0.35,
    "fade_in_seconds": 0.35,
    "fade_out_seconds": 0.7,
    "target_lufs": -27,
    "gain_db": 0,
    "ducking": true
  },
  "cover": {
    "title": "短、明确、不能虚构的封面标题",
    "image": "assets/images/cover.png"
  },
  "cta": {"type": "comment-keyword", "text": "评论区留下关键词"},
  "scenes": [
    {
      "id": "s01",
      "role": "hook",
      "text": "本分镜配音文案",
      "top_text": "可选的顶部短标题",
      "bottom_text": "可选的固定下方文案",
      "top_highlights": [{"text": "40%", "color": "#FFD400"}],
      "bottom_highlights": [{"text": "关键词", "color": "#FFD400"}],
      "visual_prompt": "不包含画面文字的完整生图提示词",
      "negative_prompt": "watermark, logo, distorted hands, rendered text",
      "images": ["assets/images/s01-01.png"],
      "media": [
        {
          "path": "assets/library/community.mp4",
          "type": "video",
          "start": 1.2,
          "record_id": "library-record-id",
          "source_relative_path": "files/视频/商务人物与活动/community.mp4"
        },
        {"path": "assets/images/s01-01.png", "type": "image"}
      ],
      "audio": "assets/audio/s01.wav",
      "audio_duration": null,
      "duration": null,
      "motion": "zoom-in",
      "transition": "dissolve",
      "caption_chunks": [],
      "sfx": []
    }
  ],
  "render": {
    "output": "output/final.mp4",
    "video_codec": "libx264",
    "audio_codec": "aac",
    "crf": 18,
    "preset": "medium",
    "subtitle_font": "Microsoft YaHei",
    "subtitle_font_size": 70,
    "subtitle_margin_v": 250
  }
}
```

## Scene roles

- `hook`: earn attention immediately with the audience's situation or contradiction.
- `problem`: make the cost or friction concrete without exaggeration.
- `explanation`: show cause, mechanism, comparison, or proof supported by the copy.
- `solution`: explain the offer, method, or next step.
- `cta`: request one simple action consistent with the copy.

## Supported render values

- `motion`: `zoom-in`, `zoom-out`, `pan-left`, `pan-right`, `static`.
- `transition`: `cut`, `dissolve`, `dip-black`, `push`.
- `sfx` item: `{"path":"assets/sfx/hit.wav","offset":0.15,"gain_db":-10}`.

`media` is optional and takes precedence over `images`. Each item may be a path
string or an object with `path`, optional `type` (`image` or `video`), and an
optional video `start` offset in seconds. The renderer loops a source video only
when the allocated segment exceeds the remaining source duration. Existing
image-only manifests remain compatible through `images`.

`record_id` and `source_relative_path` are provenance fields. The renderer
ignores them, but the workflow must preserve them for library-sourced assets.
Only copy records whose indexed `状态` equals the configured
`material_library.required_status` (normally `可使用`).

Unknown values must fall back to `static` or `cut` and be recorded in the render report instead of crashing a completed project.

## Supported layouts

- `full-frame`: default; the image fills the entire canvas and captions use the standard lower safe area.
- `text-media-text`: top scene title, framed media in the middle, and timed captions or fixed text below. Read [layout-templates.md](layout-templates.md) for the configurable region, colors, type sizes, and per-scene fields.

`text-media-text` supports two variants: `native-bold` for strong native-feed titles with outlined keyword highlights and a blurred-media background, and `classic` for the original restrained solid-background card treatment. `native-bold` is the default for new structured-layout projects. Scene highlight arrays accept strings or objects shaped as `{"text":"40%","color":"#FFD400"}`.

An unsupported layout falls back to `full-frame` and is recorded in `render_report.warnings`.

## Videos without narration

Set `"voice": {"enabled": false}` and give every scene a positive `duration`. The renderer does not require `audio` or `audio_duration` in this mode and emits a silent 48 kHz mono AAC track for platform compatibility. Sound effects may still be supplied per scene.

## Background music

- Omit `bgm`, set it to `false`, or set `bgm.enabled` to `false` for no music.
- `enabled: "auto"` means the orchestration workflow may select a track when the
  user has not explicitly requested silence. The renderer does not search a
  remote library by itself; `bgm.path` must already resolve to a copied local
  project file.
- Supported `loop_mode` values are `crossfade` and `hard`. Crossfade is the
  default.
- Default `target_lufs` is `-27` with narration and `-18` without narration.
  These are starting points; listen and lower the bed when speech is masked.
- `ducking` defaults to true when narration is enabled. Final output is stereo
  AAC even when scene narration is mono.

## Generated fields

The TTS helper adds `tts_text_sha256`, `tts_settings_sha256`, `tts_request_id`, `audio_duration`, `duration`, and `tts_status`. The renderer may add `timeline_start`, `timeline_end`, `render_status`, BGM loop/render fields, and a top-level `render_report`, including the resolved `layout_variant`, `background_mode`, and BGM summary.
