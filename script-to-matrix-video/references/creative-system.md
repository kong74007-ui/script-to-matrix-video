# Creative system

Read this reference before storyboarding, material selection, and image generation.

## Default direction

Use **native-feed problem-solution light motion**. The piece should feel like useful content made for the feed, not a glossy TV commercial and not an animated slide deck.

### Global visual bible

Write one paragraph covering:

1. Audience and emotional temperature.
2. Subject or recurring character consistency.
3. Realistic location and production design.
4. Palette, contrast, lighting, and texture.
5. Lens, camera distance, and depth of field.
6. Graphic overlays and caption-safe negative space.
7. Excluded styles and artifacts.

Reuse the paragraph unchanged inside every scene prompt. Add scene-specific content after it.

Use the same paragraph as a visual-selection checklist for supplied and library
assets. A metadata match is not enough: the actual frame must belong to the same
audience, realism level, palette, setting, and emotional temperature as the
video.

### Scene prompt shape

```text
[global visual bible]
Narrative function: [hook/problem/explanation/solution/cta].
Scene: [specific visible subject, action, environment, emotion, and useful props].
Composition: vertical 9:16, [shot size], subject positioned to preserve subtitle-safe negative space.
Continuity: [same character/product/palette/time of day as adjacent scenes].
No rendered words, captions, logos, watermarks, UI chrome, or unsupported claims.
```

## Storyboard rhythm

- Open with a recognizable situation, surprising contrast, or concrete pain point; avoid a generic title card when an image can communicate the hook.
- Change the visual idea when the narration changes meaning, not at every punctuation mark.
- Use an extra asset inside a scene only for a comparison, reveal, detail, or before/after relation.
- End with one visual action supporting the CTA. Do not show multiple competing actions.

## Motion mapping

| Narrative need | Preferred motion |
|---|---|
| Reveal a problem | slow zoom-in |
| Add context | gentle pan |
| Explain a solution | stable frame with one controlled push |
| Compare two ideas | direct cut or short dissolve |
| Deliver CTA | settle to near-static for readability |

Use motion as emphasis. Do not randomize every scene independently. Alternate only when it supports the content and preserves a coherent motion grammar.

## Music mapping

- Choose BGM from the full-copy topic and emotional arc, not from one scene
  keyword.
- Knowledge and lead-generation content normally needs restrained, ordinary,
  contemporary music rather than sci-fi, trailer, or cinematic spectacle.
- With narration, prefer instrumental tracks with modest midrange activity and
  enable ducking. Without narration, music can carry more energy but must not
  overpower readable text.
- One track per short video is the default. Change tracks only when the copy has
  a genuine chapter or emotional break.

## Subtitle and overlay rules

- Add all readable text during compositing, never inside generated images.
- Use high-contrast simplified Chinese, a strong outline or shadow, and no more than two lines.
- Keep the lower platform-control zone and upper account-header zone clear.
- The cover title should be one claim or question, usually 8–16 Chinese characters, supported by the copy.

For `text-media-text` with the `native-bold` variant, rewrite the displayed title as an intentional 2–4-line hierarchy without changing its factual meaning. Use explicit newlines to separate context, comparison, and conclusion. Highlight only the decisive numbers, contrast term, or CTA keyword; do not color every noun. The generated image remains text-free and should be composed for a near-full-width central crop.

## CTA constraints

Preserve a CTA in the customer's copy. Otherwise select one allowed action at random, record the selection in the manifest, and keep it stable across rerenders. Never invent scarcity, coupons, guaranteed outcomes, or regulated claims.
