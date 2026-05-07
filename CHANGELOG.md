## Unreleased

### BREAKING CHANGE

- `GetSuggestionAnnotationsRequest`: `repeated string texts` replaced with
  `repeated SuggestionInput suggestions`. Each input carries the text plus
  optional `page_number` (0-indexed; omitted = all pages — preserves Pro's
  existing behaviour) plus opaque metadata fields (`reason`, `confidence`,
  `explanation`, `recommendation`) that are echoed onto each output annotation.
- `GetSuggestionAnnotationsResponse`: `repeated SuggestionResult results`
  (per-text aggregate counts) replaced with `repeated Annotation annotations`
  (per-rect entries with coords + echoed metadata). The aggregate
  `total_suggestions` count is renamed to `total_annotations` to match its
  semantics (count of rects, not inputs). The `xfdf` field is unchanged.
- New `SuggestionInput` and `Annotation` proto messages. `SuggestionResult`
  is removed.

Coordinated release required — Pro and platform must regenerate stubs and
update their callsites in the same release window.

## v0.4.0 (2026-05-04)

### Features

- add MergePdfs RPC for bundle composition

## v0.3.0 (2026-04-30)

### Features

- detect risky annotations RPC (#1)

## v0.2.1 (2026-03-12)

### Bug Fixes

- adjust overaly spacing and margins

## v0.2.0 (2026-03-11)

### Bug Fixes

- prevent existing redaction markers from interfering with new ones

### Features

- add verify redactions rpc

## v0.1.1 (2026-03-04)

### Bug Fixes

- use generate redaction id instead of uuid in suggest
- update redaction id truncation and resize strategy

## v0.1.0 (2026-02-24)

### Features

- welcome to pdf-core
