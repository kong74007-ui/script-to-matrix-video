# Layout templates

Read this reference when creating or editing a text-media-text project.

## Default

Use template 1 unless the user chooses another:

    {"layout": {"template_id": "black-left-bold"}}

The eight standard IDs are listed in [style-templates.md](style-templates.md). The standard catalog owns typography, background, top position, media rectangle, CTA position, and semantic-emphasis styling. Prefer a template_id over duplicating the full layout object.

The additional 18 `ref-` IDs are listed in [reference-typography-templates.md](reference-typography-templates.md). They preserve five independent text layers and use the dedicated HyperFrames wrapper; do not pass them to `render_video.py`.

## Structural contract

Every bundled template follows the same three-region structure:

1. Top: persistent title block.
2. Middle: supplied or approved-library image/video material.
3. Bottom: persistent subtitle or CTA.

Shared defaults:

- preset: text-media-text;
- variant: native-bold;
- background_mode: solid;
- visible top margin around 96px (5%);
- media rectangle x=24, y=620, width=1032, height=930;
- fixed CTA near y=1730;
- media_border_width: 0, divider_height: 0, and empty surface_boxes;
- text_pop_in: false.

Do not add a divider, background blur, progress bar, player chrome, or fade-in unless the selected template explicitly defines that text treatment. The 18 reference templates may use colored text bands, rounded media cards, or button-like CTA backgrounds because those are part of their approved typography.

## Copy fitting

- Preserve the user's wording and explicit line breaks when they fit.
- Keep a standard template's top copy to at most three lines and its CTA to one line when possible.
- For a `ref-` template, split the hook into `top1`/`top2`/`top3` and the CTA into `bottom1`/`bottom2`; leave an unused layer empty rather than duplicating text.
- If copy does not fit at the template's minimum font size, shorten or split it instead of clipping or shrinking it into unreadable type.
- Render title and CTA at full opacity from the first frame.
- Preserve the selected left, center, or right alignment; do not silently center a right-aligned template.

## Media

Use at least two distinct assets for an 8–10 second output and include approved video by default. Template mode must use client files or library records marked 可使用; AI media generation is forbidden.

## Project-level overrides

Explicit overrides are allowed for copy-specific fitting, but they must preserve the selected template's recognizable layout. Safe standard-template overrides include font size within readable bounds, line limits, material crop, and top/bottom text positions. Do not turn an override into an undeclared template. The reference pack's font sizes, colors, strokes, positions, and layer hierarchy are fixed; shorten or split copy instead of altering them.
