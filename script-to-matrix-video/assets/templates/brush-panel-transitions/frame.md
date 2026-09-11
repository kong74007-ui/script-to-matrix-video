# Design

Canvas 1080x1920. Black #000000. Middle stage x0 y656 width1080 height608. Square corners, no frame or border. Upper/lower black bars remain entirely black except our own type.

Static upper copy centered, top96px (5%), width996, left42; headline96px and subtitle82px, body62px; Noto Sans SC local variable font weight900, tracking-0.025em. Red #d51b08 with cream #fff3ca outer stroke11px on headline/CTA; yellow #ffe018 with black stroke4px for supporting lines. Short black shadow only. CTA86px centered bottom116px. Never apply motion/fade to text.

Picture-only transitions: exact circle/shape masks, brush-like ragged diagonal edge, staggered eight vertical strips, square/diamond apertures. White #ffffff permitted inside the middle band during reference-derived reveal only. No new decorative colors, color grade or bloom. Natural Rec709 footage after explicit HLG normalization.

Use iris-reveal registry circle geometry (plain register, no rim/dimming). Custom geometry required for the reference-specific brush/slat/diamond sequence; catalog words search did not provide these moves. Recipes: transitions/css-radial.md and css-cover.md, registered GSAP adapter.
