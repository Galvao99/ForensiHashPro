# Document Date × Metadata Deterministic Rule V1

## Objective and canonical flow

`case.document_date_metadata_temporal_relation` version 1 records only the
temporal relation demonstrable between one canonically selected document date
and one supported document-metadata timestamp from the same artifact.

The rule runs in the existing flow:

`AnalysisResult(s) → providers → EvidenceGraph → CaseEvidenceIndex → deterministic rule → CaseResult → presentation model → Summary/Explorer`

It consumes `CaseEvidenceIndex`. It does not read files, run OCR, parse metadata,
rerun ContractDate, or execute in the UI.

## Sources and semantic roles

The document side is the single Timeline event classified by ContractDate V2
as `contract_date`, projected canonically as `document_date`. ContractDate V2
extracts valid textual dates and ranks them with its existing deterministic
context vocabulary. Native/OCR origin, raw text, normalized value, source
offset, context, precision, timezone state, provider, and available page remain
attached to the canonical occurrence. ContractDate V2 currently resolves equal
scores by source position; V1 characterizes and reuses that existing primary
selection rather than duplicating or redesigning it.

Supported metadata roles are:

- `pdf_creation_date`: PDF `CreationDate`/`CreateDate`;
- `pdf_modify_date`: PDF `ModDate`/`ModifyDate`;
- `xmp_create_date`: XMP `CreateDate`;
- `xmp_modify_date`: XMP `ModifyDate`;
- `xmp_metadata_date`: XMP `MetadataDate`;
- `metadata_creation_date`, `metadata_modify_date`, `metadata_date`: compatibility
  roles for legacy ungrouped fields, whose exact field remains explicit in
  provenance and is not relabelled as PDF or XMP.

Group-qualified fields outside the PDF/XMP whitelist do not acquire one of
these roles. Filesystem created/modified/accessed times, signing time,
certificate validity, arbitrary OCR/body dates, and JSON timestamps are not
metadata inputs to this rule.

The metadata adapter uses the existing `TemporalParser` before assigning a
supported role. This is necessary because the graph intentionally deduplicates
the Timeline derived view against the primary metadata occurrence; both
projections therefore carry the same role, precision, and timezone state.

## Precision policy

Every parsed value is expanded to a half-open interval `[start, end)` using
only its declared precision:

- year: start of the year to start of the next year;
- month: start of the month to start of the next month;
- day: midnight to midnight of the next civil day;
- minute, second, millisecond, microsecond: one unit at that precision.

Consequently, document date `2021-03-05` (day precision) and metadata
`2021-03-05T14:32:18` overlap. The rule does not manufacture a document time of
midnight and does not report a false 14-hour delta. V1 does not display an
exact delta because a lower-precision interval cannot support that precision.

## Timezone policy

- aware × aware: interval boundaries are compared as UTC instants;
- naive × naive: boundaries are compared in the civil-time domain;
- aware × naive: no finding;
- missing/unknown timezone remains unknown and is never replaced with the
  Windows, machine, user, country, or inferred timezone.

The raw and normalized representations, precision, and timezone status remain
available through the two supporting occurrence IDs.

## Relations and epistemic state

V1 emits one of these factual `relation_type` values:

- `document_date_before_metadata`;
- `document_date_after_metadata`;
- `temporal_overlap`.

The `CaseFinding` state is `OBSERVED`, not `MATCH` or `MISMATCH`. Earlier/later
values are not described as divergence or inconsistency. Every finding uses
`INFO` severity and a neutral statement naming the exact metadata field.

Finding identity is deterministic over rule ID/version, artifact ID, document
occurrence ID, metadata occurrence ID, metadata semantic role, and temporal
relation. Discovery order, UI row, display text, memory, and execution time are
not identity inputs.

## Ambiguity, absence, and failures

The rule requires exactly one canonical `document_date` occurrence in an
artifact. If multiple eligible occurrences reach the index, it does not choose
the first, oldest, most frequent, or highest-confidence value. Each supported
metadata occurrence is compared separately, so PDF and XMP fields retain their
own identities and provenance.

No finding is emitted when either side is absent, a value is malformed,
precision/timezone provenance is missing or inconsistent, timezone domains are
incompatible, or the document date is ambiguous. These are normal limits of
available evidence, not `MISMATCH` and not operational failures. A
`RuleExecutionLimitation` remains reserved for an actual exception isolated by
the canonical pipeline.

## Provenance and presentation

`CaseResult` contains both supporting occurrence IDs and their fact IDs plus
the exact fields, roles, raw/normalized values, precision, timezone state, and
relation. The occurrences retain provider/parser, metadata key/XMP group,
native/OCR source, page when available, text offset/context, and artifact
identity. No provenance is invented where the upstream producer did not
provide it.

The Summary only indicates that the verification exists. Explorer details show
the compared field, values, relation, precision, timezone, sources, and
available locators by resolving those same occurrences. The presenter is a
pure projection of `CanonicalCasePipelineResult`; navigation, search, filtering,
and selection never execute the rule.

## Performance

`CaseEvidenceIndex` is built once. The rule performs one indexed lookup per
supported semantic role, groups results by artifact, and deterministically
sorts only each artifact's candidates. Approximate evaluation cost is
`O(d + m + Σ m_a log m_a)`, where `d` and `m` are indexed document and metadata
occurrences. There is no pairwise cross-artifact scan and no additional file
I/O.

## Non-inferences and limitations

Metadata timestamps are technical observations and are not, by themselves,
proof of document creation, alteration, authenticity, authorship or fraud.

In particular, `CreationDate` is not a legal or factual assertion of when the
document was created, and `ModDate`/XMP `ModifyDate` do not prove that document
content was altered. V1 does not infer fraud, manipulation, authenticity,
falsity, authorship, legal validity, evidentiary relevance, importance,
confidence, or a suspicious score.

Known upstream limitation: the current ContractDate V2 Timeline projection
retains a global text offset/context and overall native/OCR source, but does not
always resolve that offset back to a page segment. V1 preserves the available
coordinates and does not guess a page. Improving that projection requires a
separate, characterized ContractDate provenance patch.
