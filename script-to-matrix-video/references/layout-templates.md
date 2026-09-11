# Retained local template layouts

The eight standard FFmpeg typography presets were removed on 2026-09-10. Do not restore them from old examples or select their IDs. The empty `assets/templates/catalog.json` records retired IDs for clear error reporting; it is not a selectable catalog.

## Offline template selection

- Ordinary local template jobs default to `ref-15-tianjin-monochrome` (天津黑白极简). The city in the template name describes its reference, not a restriction on the user's copy.
- Read [the reference pack](reference-typography-templates.md), choose an existing ID from its manifest, map copy into `top1/top2/top3/bottom1/bottom2`, and use `scripts/render_reference_typography.py`. Do not pass ref IDs to `render_video.py`.
- Reference jobs use three distinct approved video files, random integer 8–15 seconds assigned once per job, fixed typography, and first-frame text. Keep library BGM rotation for offline batches.
- Explicit motion-template requests use [nine-grid](nine-grid-reveal.md), [triple-strip](triple-strip-shutter.md), or [yellow-banner](yellow-banner-zoom.md). Preserve each template's timing, motion and bound BGM.
- Never generate AI media for template jobs. Select only supplied or approved-library assets. Keep fonts and media framing defined by the chosen retained template.

## Low-level renderer compatibility

`render_video.py` remains available for full-script videos and explicit custom layouts described by [the project schema](project-schema.md). A raw `layout.preset: text-media-text` is a custom renderer configuration, not another bundled template. Removed template IDs fail rather than falling back.

The deployed platform has a separate live catalog and routing contract. These offline defaults do not change its catalog or authorize deployment.
