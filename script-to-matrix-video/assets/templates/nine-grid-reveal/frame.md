# 九宫格开场 → 全屏品牌展示

## Design truth

Keep the supplied reference's media structure and timing, with both text regions visible from frame 0.
Canvas 1080×1920. Palette: #000000 background/gutters/shadows and #ffffff type.
Nine equal 360×640 portrait cells on a full-bleed 3×3 grid, with 3px black separators.
Cells appear fully opaque at frame-accurate boundaries. No card motion, rounding, colored panels, or decorative UI.
After 3.2s, use a full-frame portrait video; no top/media/bottom blocks.
Title: centered around y=248 (12.9% height), Noto Serif SC bold 900, 82px, white with thin black stroke and small lower-right shadow, up to 9 Han characters. Side dashes are part of the label treatment, not a frame divider.
Bottom short phrase: centered around y=1640 (85.4% height), Noto Sans SC 900, 58px, white with black stroke/shadow. No badge or colored backing. Both text regions are fully visible from frame 0 through the end of the 12-second composition, without text animation.
Opening impact: exactly one enlarged media frame (scale 1.17, canonical media Blur 0.10) at 3.2s, then normal full-frame media with Blur returned to 0. It is not a multi-second zoom of the whole nine-grid.
Source photography supplies color and detail. No independent grade, extra decoration, or AI image generation.
Soundtrack: the bundled 12-second reference-bgm.m4a is bound to this template, starts at 0s at volume 1, and is copied byte-for-byte. It is not a job variable and does not participate in random or batch BGM selection.
