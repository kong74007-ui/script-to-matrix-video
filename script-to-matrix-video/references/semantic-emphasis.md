# Semantic emphasis for template videos

Read this reference before producing a `text-media-text` project that needs AI-selected large type or keyword emphasis.

## Responsibility boundary

- The calling Agent decides **which exact source spans matter** and writes `emphasis.v1`.
- The selected `template_id` decides **how those spans look** through the catalog's `emphasis_profiles` map.
- The renderer validates, lays out, and draws the result. It never calls a model.

Codex is the internal provider. A future Huangque Agent may replace it by emitting the same object; the renderer and templates do not change.

## Contract

```json
{
  "emphasis": {
    "schema_version": "emphasis.v1",
    "provider": "codex",
    "source_hash": "sha256...",
    "prompt_version": "v1",
    "top": [
      {
        "start": 7,
        "end": 10,
        "text": "一样大",
        "role": "contrast",
        "priority": 1,
        "confidence": 0.95
      }
    ],
    "bottom": []
  }
}
```

`top` and `bottom` offsets are zero-based Python string offsets into the first persistent `scene.top_text` and `scene.bottom_text`. Preserve that copy exactly. Calculate `source_hash` as SHA-256 of this canonical UTF-8 JSON, with sorted keys and compact separators:

```json
{"bottom":"<exact bottom_text>","top":"<exact top_text>"}
```

Use `template_policy.emphasis_source_hash(top_text, bottom_text)` when building a project programmatically.

Supported roles are `number`, `contrast`, `pain`, `benefit`, `conclusion`, and `cta`. Priority `1` is strongest. Confidence must be from `0` through `1`; spans below `0.6` are ignored. Each region keeps at most three non-overlapping spans.

The renderer rejects or drops rewritten text, stale hashes, out-of-range offsets, unsupported roles, overlaps, and excess spans. If the semantic object is absent or invalid, deterministic rules may highlight numbers, money, percentages, dates, quoted phrases, contrast clauses, and CTA phrases. It never invents or rewrites copy.

## Precedence and fitting

1. A scene's existing `top_highlights` or `bottom_highlights` remains the strongest explicit override.
2. A valid top-level `emphasis.v1` is next.
3. Deterministic fallback runs only when no valid semantic object controls the region and `auto_highlight` is enabled.

The renderer protects emphasized phrases from automatic line breaks. It first wraps and sizes the base copy, then applies the template profile. If the highlighted run would overflow, it reduces the emphasis scale, then the base font size, and finally removes only the extra scale. It never truncates the source text.

`emphasis_profiles` may set `scale`, `min_scale`, `color`, `outline_width`, `outline_color`, `underline`, `italic`, `bold`, `angle`, and per-role colors. Keep these visual settings in the catalog; providers must not emit styling instructions.
