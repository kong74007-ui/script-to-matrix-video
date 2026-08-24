# Template batch validation

Read this reference before rendering more than one `text-media-text` output. The validator makes duration, media variety, video-first selection, A/B differences, and BGM rotation deterministic across computers.

## Batch manifest

Create one project manifest per output, then create a batch JSON beside them:

```json
{
  "bgm_policy": {"allow_mixed_enabled": false},
  "jobs": [
    {
      "job_id": "01-A",
      "copy_id": "01",
      "variant_id": "A",
      "project": "projects/01-A/project.json"
    },
    {
      "job_id": "01-B",
      "copy_id": "01",
      "variant_id": "B",
      "project": "projects/01-B/project.json"
    }
  ]
}
```

Paths are relative to `batch.json`. A `projects` array of path strings is accepted for simple batches, but include `copy_id` and `variant_id` when producing A/B variants so duplicate media sets can be detected.

Every project manifest must stay inside the folder that contains `batch.json`; absolute paths and `..` escapes are rejected. Run validation before starting render workers. Both validator and renderer use optimistic file snapshots plus an exclusive save lock, so a project changed by another process fails instead of silently overwriting the newer manifest.

## Required preflight

```powershell
python scripts/validate_template_batch.py "D:\video-project\batch.json" --fix-duration --report "D:\video-project\batch-validation.json"
```

`--fix-duration` only extends project durations to the copy-based target. It never invents, substitutes, or downloads media and never changes BGM. A nonzero exit code means the batch is not ready to render.

Projects may select a bundled style with `layout.template_id`. The validator resolves the same catalog as the renderer before checking `layout.preset`, then reports the resolved `template_id` per job. Do not expand and duplicate the full template object into every batch manifest.

The validator rejects:

- a duration below `max(8 seconds, reading time + 1.5 seconds)`;
- fewer than two distinct assets through 10 seconds, fewer than three above 10 through 15 seconds, or fewer than four above 15 seconds;
- image-only selection without an explicit documented fallback;
- A/B variants of one copy that use the same full media set;
- fewer than two distinct BGM tracks across two or three BGM-enabled outputs;
- fewer than three distinct BGM tracks across four or more BGM-enabled outputs;
- consecutive BGM-enabled jobs that reuse the same track.
- a batch that enables BGM on only some outputs unless `bgm_policy.allow_mixed_enabled=true` explicitly records that mixed plan.

Use each library record's `record_id` in `media` and `bgm`. When `record_id` is absent and a local file exists, the validator hashes the file so copying the same asset under different names cannot bypass the checks.

After validation passes, render project manifests with safe concurrency and write the separate timing/status report required by the main Skill workflow.
