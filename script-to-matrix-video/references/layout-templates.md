# Layout templates

Read this reference when creating or editing a text-media-text project.

## Default

Use template 1 unless the user chooses another:

    {"layout": {"template_id": "black-left-bold"}}

The eight valid IDs are listed in [style-templates.md](style-templates.md). The catalog owns typography, background, top position, media rectangle, CTA position, and semantic-emphasis styling. Prefer a template_id over duplicating the full layout object.

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

Do not add a yellow divider, background blur, decorative card, kicker, progress bar, player chrome, or fade-in unless the user explicitly asks to leave the eight-template system.

## Copy fitting

- Preserve the user's wording and explicit line breaks when they fit.
- Keep top copy to at most three lines.
- Keep the CTA to one line when possible.
- If copy does not fit at the template's minimum font size, shorten or split it instead of clipping or shrinking it into unreadable type.
- Render title and CTA at full opacity from the first frame.
- Preserve the selected left, center, or right alignment; do not silently center a right-aligned template.

## Media

Use at least two distinct assets for an 8–10 second output and include approved video by default. Template mode must use client files or library records marked 可使用; AI media generation is forbidden.

## Project-level overrides

Explicit overrides are allowed for copy-specific fitting, but they must preserve the selected template's recognizable layout. Safe overrides include font size within readable bounds, line limits, material crop, and top/bottom text positions. Do not turn an override into an undeclared ninth template.
