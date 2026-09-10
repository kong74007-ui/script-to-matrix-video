# 黄条标题·变幅冲击

## Frame and palette

1080×1920. Measured reference coordinates scaled from 720×1280 by 1.5.
Accent #FAE108; black #000000; white #FFFFFF; body panel rgba(0,0,0,.42).
Natural Rec.709 footage; no brightness lift, white flash, saturation shift or LUT.
All rectangular corners square. No app chrome, separators, badges or extra shapes.

## Typography

Bundled Noto Sans SC variable: title 900/81px, subtitle 900/63px, source label 800/45px, body 750/48px.
Footer bundled Noto Serif SC 700/45px. Black outline subtitle 9px, source label 6px, footer 6px; paint-order stroke fill. No text motion.
Title banner x108 y199.5 w864 h138; title centered, dynamically shrink only if text exceeds 804px.
Subtitle x90 y358 w900 h156, two independent centered rows with 74px line-height. Reference-tight row spacing uses a narrow intentional nominal-font-box overlap annotation; visible glyphs remain separated.
Source label x118.5 y532 w450 h64, left aligned.
Body panel x121.5 y1335 w835.5 h203, vertical padding15 and horizontal padding24, line-height55.5, left aligned; fixed geometry with text fit lower bound28px for longer copy.
Footer x99 y1580 w882 h90, centered. Empty optional text fields hide their own contents only.

## Media / motion

Shared canvas/motion state, persistent DOM typography.
Slots [0,86), [86,183), [183,302), 30fps. Hard identity switches with radial zoom blur, not crossfades.
Slots1/3: central16:9 band, base1080×607.5 centered at540,960; same-source full-frame canonical blur behind it.
Slot1 band expands from44% to100% byf25; then to118% byf80; outgoing zoom/blurf81–85.
Slot2 full-frame punch settles rapidly; no forced sideways rotation; outgoing burstf180–182.
Slot3 overshoot onf183, compressedbandf184 then settles byf208 and holds toend.
Radial effect media-only, based on registry cinematic-zoom sampling primitive with no RGB offset/white flash. BGM exactboundreferenceAAC.

## Acceptance

First and last frames show text and validfootage, no blacktail. Three different approvedlibraryfiles. Body fits panel; title never clips. Color tagsBT709. BoundaudioSHAverified.
