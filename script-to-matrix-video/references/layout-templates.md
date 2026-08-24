# Layout templates

Read this reference when a video should use a structured page layout instead of full-frame media.

## Bundled style catalog

For an authored visual style, select one entry from [style-templates.md](style-templates.md) with a stable `template_id`:

```json
{"layout": {"template_id": "business-black"}}
```

The renderer reads `assets/templates/catalog.json`, applies that template's `layout` and `render` defaults, then applies explicit project fields. This means a project can select one template and override only the one value it needs. The batch validator resolves the same catalog before enforcing duration, media, A/B, and BGM rules.

The bundled templates may use `top_font`, `bottom_font`, a persistent `kicker`, and up to 24 validated `surface_boxes`. These are styling primitives only; they do not change copy, retrieve media, or bypass provenance rules. Bundled fonts load from `assets/fonts` automatically.

## `text-media-text`

Use for knowledge explainers, local-business invitations, case studies, data comparisons, tutorials, and list-style videos where the title and CTA must stay visible around the media.

This template is an independent production function, not merely a styling option inside full script-to-video. It accepts a top title plus bottom subtitle/CTA as its minimum input, works without narration by default, and supports both one-off and batch generation. Use only client-supplied media or library records whose `状态` is `可使用`; AI image and video generation are forbidden. If no suitable material exists, report `material_missing` instead of generating or using unrelated filler. For batch work, create independent output variants, preserve the meaning of each copy item, vary meaningful visual choices, and emit a timing/status report together with the MP4s.

The template has two variants:

- `native-bold`: the default for new projects. It uses strong Chinese display text, thick dark outlines, yellow/red keyword emphasis, a blurred continuation of the current image behind the text bands, near-full-width central media, and a restrained text scale-in.
- `classic`: the original warm solid-background editorial card. Use only when the user asks for a calm, minimal, or premium information-card treatment.

Do not reproduce player chrome from visual references. Play buttons, progress bars, account labels, and platform UI are not part of the rendered template.

### Duration policy

- Hard minimum total duration: 8 seconds.
- Normal target range: 8–15 seconds.
- Without narration, calculate `target duration = max(8 seconds, reading time + 1.5 seconds)`.
- Estimate reading time at about five visible Chinese characters, letters, or digits per second. Ignore whitespace and punctuation when counting.
- Round up to a valid video frame. The renderer performs the same calculation and extends a short manifest to the full copy-based target, not merely to 8 seconds.
- When the computed reading time pushes the result beyond 15 seconds, shorten the displayed copy or split it into multiple template scenes. Do not cut required wording or force unreadable speed merely to stay within 15 seconds.

### Media pacing policy

- Search approved `视频` records first, then approved `图片` records. Do not satisfy a whole template with one still image.
- Use at least two distinct assets for 8–10 seconds, at least three above 10 through 15 seconds, and at least four above 15 seconds. Repeating the same file or changing only its crop does not count as a distinct asset.
- Include at least one contextually suitable video by default. Use an image-only output only after two distinct video searches fail; record `material_policy.allow_image_only=true` and a specific `image_only_reason`.
- For A/B variants, change the media set itself. A different filename, crop, or color treatment applied to the same complete media set is not enough.

### Recommended `native-bold` configuration

Default 1080×1920 structure:

- Top information band: `y=0–500`; title center near `y=270`.
- Media region: `x=20`, `y=500`, `width=1040`, `height=940`.
- Bottom information band: `y=1440–1920`; CTA center near `y=1650`.
- Keep essential text above `y=1750` and away from the first 80 px.
- Use 2–4 intentional title lines and 1–3 CTA/caption lines.

```json
{
  "layout": {
    "preset": "text-media-text",
    "variant": "native-bold",
    "background_mode": "blurred-media",
    "background_color": "#11151C",
    "background_blur": 28,
    "background_brightness": -0.22,
    "background_saturation": 0.78,
    "band_color": "#101318",
    "top_band_opacity": 0.42,
    "bottom_band_opacity": 0.58,
    "top_text_color": "#FFFFFF",
    "bottom_text_color": "#FFFFFF",
    "text_outline_color": "#111111",
    "top_text_outline": 8,
    "bottom_text_outline": 7,
    "text_shadow": 2,
    "accent_color": "#FFD400",
    "secondary_accent_color": "#FF453A",
    "auto_highlight": true,
    "text_pop_in": true,
    "top_font_size": 80,
    "bottom_font_size": 70,
    "top_min_font_size": 52,
    "bottom_min_font_size": 46,
    "top_max_chars": 12,
    "top_max_lines": 4,
    "bottom_max_chars": 12,
    "bottom_max_lines": 3,
    "top_text_y": 270,
    "bottom_text_y": 1650,
    "bottom_text_mode": "fixed",
    "media_border_width": 0,
    "divider_height": 0,
    "divider_color": "#FFD400",
    "media": {
      "x": 20,
      "y": 500,
      "width": 1040,
      "height": 940
    }
  }
}
```

Write each scene's display copy with intentional line breaks and a small number of highlights:

```json
{
  "top_text": "大健康行业私域复购率 40%\n美妆只有 15%\n选赛道这件事\n数据不会骗人",
  "bottom_text": "现在还想进军这个赛道？\n评论区回复：关键词",
  "top_highlights": [
    {"text": "40%", "color": "#FFD400"},
    {"text": "15%", "color": "#FF453A"},
    {"text": "数据不会骗人", "color": "#FFD400"}
  ],
  "bottom_highlights": [
    {"text": "关键词", "color": "#FFD400"}
  ]
}
```

When highlight arrays are absent and `auto_highlight` is true, the renderer emphasizes numbers, percentages, quoted phrases, and the short term after the final Chinese colon in fixed bottom CTA text. Explicit arrays take precedence. Keep one primary accent and one comparison accent; highlighting every phrase destroys hierarchy.

The renderer respects explicit newlines when they fit. Otherwise it wraps the complete text and reduces type size down to the configured minimum instead of silently discarding the final clause.

Use `background_mode: "solid"` when the image colors make the blurred background distracting. `blurred-media` darkens and blurs the current image behind the top and bottom bands; it does not create additional content.

### `classic` configuration

```json
{
  "layout": {
    "preset": "text-media-text",
    "variant": "classic",
    "background_mode": "solid",
    "background_color": "#F5F1E8",
    "top_text_color": "#1F2430",
    "bottom_text_color": "#1F2430",
    "accent_color": "#D97745",
    "auto_highlight": false,
    "text_pop_in": false,
    "top_font_size": 76,
    "bottom_font_size": 62,
    "top_max_chars": 12,
    "top_max_lines": 2,
    "bottom_max_chars": 14,
    "bottom_max_lines": 2,
    "top_text_y": 221,
    "bottom_text_y": 1642,
    "bottom_text_mode": "captions",
    "media_border_width": 4,
    "media_border_color": "#D8D2C8",
    "media": {
      "x": 60,
      "y": 420,
      "width": 960,
      "height": 1040
    }
  }
}
```

### Shared behavior

`top_text` is displayed for the scene. When absent, the renderer derives a short fallback from the first caption chunk.

With `bottom_text_mode: "captions"`, the bottom region shows timed `caption_chunks`. If a scene provides `bottom_text`, that fixed text replaces timed captions for the scene. With `bottom_text_mode: "fixed"`, every scene uses `bottom_text`, falling back to its narration text.

For a pure graphic template without narration, set `voice.enabled` to `false`, use `bottom_text_mode: "fixed"`, provide concise `bottom_text`, and set explicit scene durations using the duration policy above. The MP4 keeps a silent AAC track for publishing compatibility.

Supplied and library images should not contain conflicting top or bottom wording. Compose readable Chinese in the renderer. For `native-bold`, choose assets that survive a wide, near-full-width central crop. For `classic`, choose assets with more internal negative space around the subject. Never generate replacement media for this template.

## `full-frame`

This remains the default for ordinary videos. Omit `layout` or set `"preset": "full-frame"`.
