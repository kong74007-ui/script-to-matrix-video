# Style template catalog

Read this reference when the user asks to choose, compare, or batch-rotate text-media-text styles.

The Skill contains 26 approved templates in two engines:

- eight standard FFmpeg templates whose machine-readable source of truth is `assets/templates/catalog.json`;
- 18 exact HyperFrames reference-typography templates whose source of truth is `assets/templates/reference-typography-17/manifest.json`.

Select a standard template with:

    {"layout": {"template_id": "black-left-bold"}}

The renderer resolves the selected template first and then applies explicit project-level layout and render overrides.

## Available templates

| Number | template_id | Name | Best for |
| --- | --- | --- | --- |
| 1 | black-left-bold | 黑底左排粗体 | 招商、门店、观点、矩阵引流；default |
| 2 | white-center-bold | 白底居中粗体 | 知识点、方案说明、商业观点 |
| 4 | white-handwritten | 白底加粗手写体 | 个人表达、经历分享、轻商业 |
| 5 | black-playful | 黑底趣味体 | 社交传播、活动招募、轻松口吻 |
| 6 | white-left-editorial | 白底左排编辑体 | 观点、行业判断、品牌叙事 |
| 7 | black-right-modern | 黑底右排现代体 | 反常识钩子、结论先行、商业口播 |
| 8 | white-left-playful | 白底左排趣味体 | 社交话题、轻知识、活动招募 |
| 9 | black-center-editorial | 黑底居中编辑体 | 品牌观点、趋势洞察、高级感表达 |

The additional stable IDs are listed in [the 18-template reference pack](reference-typography-templates.md). They run through `scripts/render_reference_typography.py`, not `scripts/render_video.py`.

No other bundled template_id is supported. Do not invent, alias, or silently fall back from a removed template.

## Shared structure

Every bundled template follows the same top-text / middle-media / bottom-text structure. The 18 reference templates may split the top into three independently styled text layers and the bottom into two independently styled text layers. `ref-18-beauty-private-domain` uses straight-edged full-frame video, large pink and white Song-style top copy, and an offset two-line lower block; it does not reproduce the rounded app-card container from its screenshot reference.

- 1080×1920 vertical canvas.
- Visible top margin is about 5% (96–100px).
- Persistent top copy, central approved material, fixed bottom CTA.
- Background is pure black or pure white.
- No template decorations, surface boxes, separators, media borders, blur, or text fade-in.
- Function 2 still requires multiple approved library/client assets and may not generate AI media.

## Semantic emphasis

Each template owns its colors and scale through the catalog's emphasis_profiles. Providers emit only neutral [emphasis.v1](semantic-emphasis.md) spans. Use emphasis sparingly: one or two decisive phrases in the title and the CTA keyword.

## Fonts

The Skill bundles and validates the font files it uses:

- Noto Sans SC (also resolves the Microsoft YaHei compatibility alias);
- Ma Shan Zheng;
- ZCOOL KuaiLe.

Do not depend on an unbundled machine-specific font.
