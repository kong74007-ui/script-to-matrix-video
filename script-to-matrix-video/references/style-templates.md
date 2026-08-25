# Style template catalog

Read this reference when the user asks to choose, compare, or batch-rotate visual styles for `text-media-text` output.

The catalog is `assets/templates/catalog.json`. It is the machine-readable source of truth for names, tags, bundled font roles, layout defaults, labels, and surface decoration. A project selects one style with only:

```json
{
  "layout": {"template_id": "business-black"}
}
```

The renderer merges the selected template first, then applies explicit project `layout` and `render` fields. This keeps one stable `template_id` for a future product UI while still allowing a project-specific color, media region, type size, or font override.

## Bundled templates

| `template_id` | Name | Best for |
| --- | --- | --- |
| `video-diary` | 视频日记 | 日常记录、探店、过程复盘 |
| `minimal-headline` | 极简大标题 | 观点、清单、短结论 |
| `airy-blush` | 轻透雅粉 | 美学、情绪、服务介绍 |
| `yellow-blue-pop` | 鲜黄亮蓝 | 活动提醒、知识点、年轻化清单 |
| `business-black` | 商务深黑 | 方案、复盘、专业服务 |
| `black-gold-premium` | 黑金高级 | 高客单服务、品牌、人物介绍 |
| `data-compare` | 数据对比 | 前后对照、选择题、案例结果 |
| `chinese-title` | 国风标题 | 文化、器物、节气内容 |
| `torn-magazine` | 撕边杂志 | 趋势、穿搭、专题选题 |
| `vlog-journal` | Vlog 手账 | 旅行、打卡、过程分享 |
| `bilingual-split` | 中英双语 | 品牌表达、术语解释、国际化内容 |
| `portrait-quote` | 人物金句 | 访谈、观点摘录、人物故事 |

These are original template definitions. Reference products may inform category names and information hierarchy, but do not copy their assets, icons, player chrome, CSS, or exact compositions.

## Semantic emphasis profiles

The catalog's `emphasis_profiles` map gives every `template_id` its own scale, color, outline/marker, underline, angle, and optional role colors. Providers emit only the neutral [`emphasis.v1` spans](semantic-emphasis.md); never copy visual settings into an Agent prompt or project semantic result. This lets Codex and a future Huangque Agent produce interchangeable decisions while the template remains responsible for appearance.

Use the profile as a restrained hierarchy, not decoration on every word. The renderer keeps at most three non-overlapping spans per region and reduces emphasis scale before base type when space is tight.

## Fonts

The Skill bundles four SIL Open Font License families and passes `assets/fonts` to FFmpeg/libass automatically:

- `Noto Sans SC`: functional body and business display;
- `ZCOOL XiaoWei`: editorial and refined titles;
- `Ma Shan Zheng`: Chinese-style title cards;
- `ZCOOL KuaiLe`: playful Vlog and journal emphasis.

Use `layout.top_font` and `layout.bottom_font` only when a project must override the selected template. A custom `render.fonts_dir` must point to a directory inside that project so the project remains self-contained.

With the bundled font directory, every requested family must appear in `assets/fonts/sources.json`, its file must exist, and its SHA-256 must match before dry-run, batch validation, or rendering can pass. Use a project-local custom `fonts_dir` for any other family.

## Batch rules

- Template rotation is a style change, not an A/B media substitution. Continue enforcing approved-media counts, video-first selection, duration, and BGM rules independently.
- Use the same copy and media only for a deliberate style comparison. For ordinary production variants, vary the media set as required by [template-batch.md](template-batch.md).
- Render one pilot before a large batch when a new font, unusually long bilingual copy, or project-level layout override is involved.
