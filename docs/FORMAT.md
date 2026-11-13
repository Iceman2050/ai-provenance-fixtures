# Fixture format

## Layout

```
fixtures/v1/<chain>/
  manifest.json            the chain record (see below)
  step-00-<name>.<ext>     the asset at step 0
  step-01-<name>.<ext>     the asset after transformation 1
  step-02-<name>.json      a sidecar file, when a step carries one
  ...
```

## The manifest

```json
{
  "fixture": "harbour-light",
  "version": "v1",
  "asset_kind": "png | text",
  "description": "what this chain demonstrates",
  "steps": [
    {
      "step": 0,
      "id": "original",
      "transform": "create",
      "description": "what happened at this step",
      "asset": "step-00-original.png",
      "sidecar": null,
      "asset_sha256": "<sha256 of the asset file bytes>",
      "payload_sha256": "<sha256 of the decoded payload, see below>",
      "previous_record_sha256": null,
      "expected": {"creator": "verified", "...": "..."},
      "record_sha256": "<see below>"
    }
  ]
}
```

`record_sha256` is the SHA-256 of the canonical JSON (sorted keys,
compact separators) of the step's record fields — `step`, `id`,
`transform`, `asset`, `sidecar`, `asset_sha256`, `payload_sha256`,
`previous_record_sha256`, `expected` — excluding `record_sha256`
itself. Each step after the first carries the previous step's
`record_sha256` in `previous_record_sha256`; that is the hash chain.
Editing any recorded fact about a step invalidates its record hash,
and breaking a link invalidates the chain — the checker tests both.

## Payload hashes

The payload hash binds assertions to *content*, not to file bytes:

- **PNG:** SHA-256 of the decoded RGBA pixel bytes (filters removed).
  Re-encoding the same pixels with a different filter changes the file
  hash and leaves the payload hash unchanged.
- **Text:** SHA-256 of the whitespace-normalised body (every whitespace
  run, including line breaks, collapsed to one space). Re-wrapping a
  paragraph leaves the payload hash unchanged; changing, reordering or
  removing words changes it.

## Carriage

An assertion set travels in exactly one of two ways at a step:

- **Embedded** — PNG: `tEXt` chunks with keys
  `provenance.assertion.<id>` plus `provenance.payload_sha256`.
  Text: the `--- provenance ---` header block (see
  `provenance_fixtures/textasset.py` for the exact grammar).
- **Sidecar** — a JSON file beside the asset:
  `{"assertions": [{"id": ..., "value": ...}], "payload_sha256": ...}`.

The binding (`payload_sha256` in the carriage) is the payload hash of
the content *at the moment the assertions were made* — normally step
0's payload. Later steps keep the original binding; that is what makes
their assertions go `unknown` when the content moves on.

## Statuses

For each assertion at each step the checker computes:

- **verified** — the assertion is present (embedded wins over sidecar)
  and its binding equals this step's payload hash.
- **unknown** — the assertion is present but its binding differs from
  this step's payload hash.
- **lost** — the assertion is present in neither carriage.

The manifest records the *expected* status for every assertion at every
step. The checker fails the run when a computed status differs, when
any asset or payload hash differs from the record, when a record hash
does not recompute, or when a chain link is broken.

## What a status does and does not mean

`verified` means: these bytes match this record, and this claim was
bound to these bytes. It does not mean the claim is true, that the
named creator made the content, or that the content is authentic in
any broader sense. Anyone can write a header that says anything; this
format only makes the claim's *carriage and binding* testable.
