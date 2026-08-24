---
name: script-to-matrix-video
description: Create publishable multi-platform 9:16 Chinese lead-generation MP4s through two independent functions. Function 1 is full script-to-video with semantic storyboarding, approved image/video/BGM retrieval with AI-image fallback, optional Alibaba Cloud CosyVoice narration, subtitles, motion, transitions, and a first-frame cover. Function 2 is `text-media-text` template video with a persistent top title, centered client-supplied or approved-library media, bottom CTA, optional BGM, no narration by default, and single or batch variants; AI-generated media is forbidden in this function. Use for 文案一键成片、模板成片、上文字中素材下文字、批量矩阵视频、素材库自动剪辑、AI 图片口播视频 or 矩阵引流视频. Do not use for manual frame-accurate editing of supplied footage.
---

# Script and Template Matrix Video

Create the final MP4, not merely a storyboard. Keep intermediate project files so failed stages can resume without regenerating completed assets. Treat the following as two independent user-facing functions, not as one workflow with an incidental layout option.

## Two independent functions

### Function 1: Full script-to-video (`script-video`)

Use when the user supplies a complete client script and asks for 文案一键成片、口播视频、知识讲解、素材库自动剪辑, or a fully assembled matrix video. Analyze the full context, split it into semantic scenes, retrieve or generate scene material, optionally synthesize narration, add subtitles, motion, transitions, SFX, BGM, and a dedicated first-frame cover.

- Minimum input: the complete client copy.
- Optional input: narration preference, platform, brand assets, material-library constraints, BGM preference, CTA, and style.
- Output: one publishable MP4 by default, plus intermediates only when requested.

### Function 2: Template video (`text-media-text`)

Use when the user asks for 模板成片、上面文字中间素材下面文字, a fixed-title information card, or batch variants of that format. This function has its own inputs, workflow, and deliverables. It does not require a narration script or semantic storyboarding across a long article.

- Minimum input: top title and bottom subtitle/CTA. Accept direct text, a table, or text extracted from supplied screenshots.
- Optional input: background context, asset keywords, preferred image/video mix, BGM preference, duration, variant count, platform, and brand style.
- Default behavior: `native-bold` 1080x1920 layout, no narration, fixed top and bottom text, central client-supplied or approved-library media, no yellow divider, restrained motion, and auto BGM unless the user asks for silence. Never generate AI media for this function. Enforce an 8-second hard minimum; 8–15 seconds is the normal range.
- Single mode: generate one or more variants for one copy.
- Batch mode: accept multiple copy rows or screenshots and generate the requested number of variants per copy. Vary media choice, crop/start offset, highlight treatment, or palette without changing the copy's meaning. Render independent jobs with safe concurrency, isolate failures, and record batch start/end time, per-output render time, status, and file path in CSV or JSON.
- Output: final MP4 files; for batch work, also return a ZIP and timing report unless the user requests individual files only.
- Reference outputs: when the user asks to see examples or when visual calibration is needed, read [the template example index](references/template-examples.md). The bundled MP4s are accepted output references, not source material for new videos.

Routing rule: an explicit top/middle/bottom layout request selects Function 2. Otherwise a full client script selects Function 1. If the user supplies a long script but explicitly requests the structured template, honor the layout and use Function 2 without asking them to restate the copy.

## Defaults

- Operate in `auto` mode unless the user asks to review a stage.
- Produce one universal `1080x1920`, 30 fps, H.264/AAC master for Douyin, Xiaohongshu, WeChat Channels, Kuaishou, and similar feeds.
- Use the native-feed, problem-solution light-motion style: readable, human, direct, and less polished than a cinematic ad or slide deck.
- For Function 1, prefer client-supplied assets, then semantically relevant library records whose `状态` is `可使用`, then AI-generated images as fallback. For Function 2, stop after client and approved-library assets; AI generation is forbidden. Copy selected library files into the project before rendering.
- Generate missing images with the available AI image-generation capability only for Function 1. Do not require a third-party image API.
- Use Alibaba Cloud Bailian CosyVoice for Chinese narration by default. If the user asks for no narration, set `voice.enabled` to `false`, give every scene an explicit reading-duration, and render a silent AAC compatibility track without calling TTS.
- Include burned-in Chinese subtitles and restrained semantic sound effects.
- Set BGM to `auto` when a configured library has a suitable track and the user has not requested silence. An explicit no-BGM instruction always wins. With narration, keep music subordinate and enable ducking; without narration, use a restrained full music bed.
- Derive total duration from the copy, semantic scenes, and actual synthesized audio. Do not force a target duration.
- Generate a dedicated cover from the copy and use it as the first visible frame.
- Function 1 uses full-frame media by default. Function 2 uses the `text-media-text` layout in [the layout template reference](references/layout-templates.md), with its `native-bold` variant unless the user asks for a restrained editorial card style.
- Return only the final MP4 to the user unless they request intermediate artifacts.

## Runtime prerequisites

- Before the first render on a machine, or when diagnosing setup failures, read [the installation reference](references/installation.md) and run `python scripts/check_environment.py`. Add `--require-tts` when narration is enabled.
- Rendering requires Python 3.10 or newer plus `ffmpeg` and `ffprobe` on `PATH`.
- Alibaba narration additionally requires the Python packages in `requirements.txt` and a locally configured `DASHSCOPE_API_KEY`. Never copy the key into this Skill, a project manifest, or a distributable archive.
- Function 1 AI image generation uses the image-generation capability available to the running Codex environment. If it is unavailable, request local images instead of claiming that generation succeeded. Function 2 must not call any image- or video-generation model.
- A material library is optional. When configured, read [the material-library reference](references/material-library.md). The helper accepts command-line settings, environment variables, or the per-user `~/.codex/script-to-matrix-video/material-library.json` profile. Remote access must use an existing SSH key or agent; never put a server password in this Skill, a project, a command, or an archive.

## Inputs and inferred values

For Function 1, the only required input is the client's complete copy. Infer the topic, audience, promise, tone, visual world, CTA, and reasonable scene count. Use supplied brand assets, required wording, products, offers, disclaimers, or platform constraints when present. Treat the complete copy as retrieval context; do not select material from a scene sentence in isolation.

For Function 2, require a top title and bottom subtitle/CTA. Infer content context, visual direction, reading duration, and asset-search terms. When text comes from screenshots, extract visible copy and normalize obvious masking such as `小○子` only when the intended character is unambiguous; otherwise preserve the visible wording or ask for the missing term. Do not reproduce play buttons, progress bars, account labels, or other platform UI from screenshot references.

If the copy already contains a CTA, preserve its intent. Otherwise choose one CTA from a constrained cross-platform pool and vary its wording: comment keyword, private message, follow for the next part, or save/share. Do not invent discounts, results, credentials, or guarantees.

## Function 1 workflow

1. Create a task-owned project folder outside the Skill directory and write `project.json` using [the project schema](references/project-schema.md). Preserve source copy verbatim in the manifest.
2. Read [the complete workflow](references/workflow.md), then analyze the full copy before splitting it. Split by semantic beat, not sentence length. A scene may use one to three image assets.
3. Choose one visual bible for the whole video. Read [the creative system](references/creative-system.md) before writing image prompts, motion, transitions, captions, cover copy, or CTA.
4. If a material library is configured, read [the material-library reference](references/material-library.md), run `scripts/material_library.py inspect`, and search it per semantic scene. Consider only `可使用` records, visually inspect the strongest candidates, then copy approved images, videos, and optional BGM into the project. Preserve each `record_id` and relative source path in the manifest.
5. Generate the cover and any scene images still missing. Every prompt must combine the global visual bible with the current scene's narrative function and composition needs. Keep character, palette, lens language, and lighting consistent.
6. When narration is enabled, run `scripts/aliyun_tts.py <project.json>`. It caches successful lines, records request IDs and exact durations, and stops after the initial request plus two retries per failed scene. Never print or store the API key. Skip this stage when `voice.enabled` is `false`.
7. With narration, lock each scene duration only after TTS: `scene duration = probed audio duration + tail padding`. Without narration, set an explicit duration based on text reading time and visual complexity. Treat the resulting duration as the source of truth for motion, captions, and the edit.
8. Add subtitle chunks, optional semantic SFX, per-asset motion, style-consistent transitions, and the resolved BGM configuration. If a structured layout is requested, read [the layout template reference](references/layout-templates.md) and record the selected layout in `project.json`. Avoid motion on every object and avoid transitions that compete with narration or music.
9. Run `scripts/render_video.py <project.json>`. It renders image and video assets, subtitles, scene audio, and the configured BGM in one resumable pass. Preserve the render report and updated manifest.
10. Inspect the opening frame, at least one middle frame, the CTA frame, and the final media probe. Confirm that captions fit safe areas, media is contextually relevant, voice is intelligible, music does not mask speech, no asset is missing, and the MP4 begins with the intended cover.

## Function 2 workflow

1. Normalize each copy item into `top_text`, `bottom_text`, background context, optional media constraints, requested variant count, and BGM preference. Preserve the user's wording and CTA intent.
2. Read [the layout template reference](references/layout-templates.md) and create one project manifest per output variant. When narration is disabled, calculate `target duration = max(8 seconds, visible-copy reading time + 1.5 seconds)`. Use approximately five visible Chinese characters, letters, or digits per second; ignore whitespace and punctuation. The normal target is 8–15 seconds. If reading needs more than 15 seconds, shorten or split the copy instead of forcing it into 15 seconds.
3. Analyze the complete title and CTA together before searching. Use only client assets or library images/videos marked `可使用`. Never call AI image/video generation, even when no candidate matches. Select ordinary, contextually relevant knowledge-video material rather than futuristic filler.
4. Build deliberate variants. Do not create duplicates by merely renaming the same render; change at least one meaningful visual dimension while preserving the copy.
5. Add optional BGM, restrained SFX, subtle media motion, and readable highlight hierarchy. Keep `divider_height` and `media_border_width` at `0` unless the user explicitly requests a separator or border.
6. Run `scripts/render_video.py <project.json>` for each job. For batch work, limit concurrency to machine capacity, keep a separate manifest and render report per job, and continue other jobs when one fails.
7. Inspect the top text, central crop, bottom CTA, first frame, final probe, audio presence, and media provenance. Reject any Function 2 output whose media is not traceable to a supplied file or a `可使用` library record. For batch work, write a timing report containing batch start/end timestamps, total elapsed time, per-file render seconds, status, and final path; package the successful MP4s and report together.

## Material and image rules

- For Function 1 AI fallback, generate portrait images at 9:16 or at enough resolution to crop cleanly to 9:16. Function 2 may only crop or reframe supplied/library media and may not generate new media.
- A scene may mix copied library videos and images through `media`. Use exact local project paths; never stream remote library files during final rendering.
- Metadata search is candidate retrieval, not creative approval. Preview candidates and reject mismatched people, locations, embedded text, watermarks, weak framing, or repeated filler.
- For Function 1 AI fallback, reserve composition space for captions and never ask the image model to render subtitle or CTA text.
- Use one to three assets only when the semantic beat benefits from a reveal, comparison, or detail cutaway. One strong asset is preferable to filler.
- In Function 1, retry a failed scene image twice. On a third failure, use a designed text card or an already generated contextually compatible asset; do not restart the whole project.
- In Function 1, record prompt, seed or generation ID when available, local path, and status in `project.json`. In Function 2, record the supplied-file path or library `record_id` for every media item.

## Timing and edit invariants

- When narration is enabled, audio duration is measured from the generated file, never estimated from character count. When narration is disabled, every scene must provide a positive explicit duration.
- A `text-media-text` video's total duration may never be shorter than 8 seconds. If a manifest requests less, the renderer extends the final scene to 8 seconds and records a warning. An explicit user duration below 8 seconds does not override this guard.
- Narration may not be cut to fit a visual. Extend or simplify the visual instead.
- Prefer clean cuts, short dissolves, subtle push/slide transitions, and match-motion handoffs. Avoid random transition packs.
- Captions should normally contain 7–14 Chinese characters per chunk and no more than two display lines. Break on meaning and punctuation.
- Keep essential text inside mobile safe areas. Do not place CTA text against platform UI zones.
- SFX should mark a real action, reveal, emphasis, or transition. Omit SFX when none improves comprehension.
- BGM should follow the overall content and emotional arc, not a single keyword. Use crossfade looping, short fades, and conservative loudness. Enable ducking when narration exists.

## Failure and cost control

- Cache artifacts by source text and settings. Reuse a successful audio or image unless its inputs changed.
- In Function 1, make at most three total attempts per generated image or TTS scene. Record the sanitized error and use the defined fallback after that.
- In Function 2, if no contextually suitable supplied or `可使用` library media exists, mark that output `material_missing` and report which semantic searches were attempted. Do not generate AI media, reuse unrelated filler, or silently switch to Function 1. Other batch jobs may continue.
- Never expose `DASHSCOPE_API_KEY`, place it in a manifest, or echo it to logs.
- Never store SSH passwords or material-library credentials in the Skill, manifest, logs, or packaged project.
- A failed scene should not invalidate other completed scenes.
- Do not make paid generation calls during dry runs, schema validation, or workflow explanation.

## Completion criteria

The job is complete only when every successful final MP4 exists and media probing confirms the requested canvas, playable H.264 video, AAC audio, and nonzero duration. For a single output, link the MP4 and briefly state its duration and resolution. For a batch, link the ZIP and timing report and state the success count, failure count, total elapsed time, and output count. Mention fallbacks only if they materially affected quality.
