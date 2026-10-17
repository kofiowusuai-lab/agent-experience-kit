# Privacy and public lessons

The public package uses synthetic examples. Lesson input must be deliberately curated: generalized failures, corrections, acceptance criteria, evidence levels, and provenance types. Do not feed raw conversations, historical agent databases, customer records, contact lists, or logs into the export workflow. There is no automatic import of private runtime history.

## Review before export

1. Rewrite the lesson as a general operational pattern. Remove names, customer identifiers, private URLs, machine paths, credentials, and distinctive details that could identify a person or project indirectly.
2. Prefer an invented example that preserves the failure mechanism without reproducing private material. Verify that any retained public material is permitted for redistribution.
3. Have a human inspect every field, including titles, provenance notes, and nested text. Mark a record public and reviewed only after that inspection.
4. Export to a separate file and inspect the resulting file before committing or sharing it. Review repository diffs and attachments too.

The exporter accepts only records with `visibility: "public"` and `reviewed_for_public: true`. Those markers are assertions supplied by the operator, not evidence of consent or a completed review.

Pattern detection provides a supplementary check for common secrets, contact details, and paths. It is not an anonymization guarantee: identifiers may evade detection, ordinary text may trigger it, and contextual combinations may reveal identity. Fix flagged records and re-review; do not remove a detector merely to force an export through.

## Local state and artifacts

Contracts, origin labels, evidence references, checks, and state can expose operational information even when artifact contents are not embedded. Evidence files and the SQLite database remain ordinary local files. The kit does not provide encryption, identity management, automatic retention, or a remote deletion service. Protect, retain, and delete them according to your environment’s policy, including any backups or copies.

Use synthetic inputs in tests and demonstrations. For any public contribution containing real data, obtain the required consent and redistribution rights, then minimize the data. A successful export does not establish those rights. If private data is accidentally shared, remove public access promptly, rotate exposed credentials where relevant, and follow the repository’s security reporting guidance.
