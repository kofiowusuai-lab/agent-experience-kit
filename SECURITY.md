# Security reporting

Do not post credentials, private evidence, customer data, or exploit details publicly.

Use the repository’s GitHub **Security** tab and private vulnerability reporting when that feature is enabled. Include the affected version or commit, a minimal synthetic reproduction, expected and actual behavior, impact, and any proposed mitigation. Never include active secrets or private runtime databases.

If private vulnerability reporting is unavailable, open a minimal public issue asking maintainers for a private reporting route. Describe only the broad issue category; omit exploit instructions, sensitive files, and identifying information. No security email address is designated by this document.

## Scope and boundaries

Relevant issues include bypasses of dependency or acceptance gates, origin isolation failures, unsafe handling of local evidence, and failures in the documented public lesson export policy. Reports about surrounding adapters should identify which behavior belongs to this toolkit and which belongs to the external runtime.

This toolkit does not execute models, browsers, provider jobs, messaging, or publishing. Boolean checks and approval records are operator assertions. Origin labels are not authentication, and file hashes only verify bytes. Deployments must supply their own access controls and protect local files and SQLite state.

The privacy detector cannot guarantee anonymization. Manual review of curated lessons remains required even when detection and export succeed. If a secret has already been exposed, revoke or rotate it through the relevant service; deleting a repository file does not revoke the secret or remove existing copies.

No response-time commitment or supported-version policy is currently promised. Maintainers will assess reports according to reproducibility and impact.

## Optional central hub

Report organization/team isolation failures, credential or session exposure, CSRF bypasses, conflicting event acceptance, projection regressions and unsafe static-file handling privately. Agent-provided metadata is untrusted input. The hub authenticates scoped provisioned credentials; operator labels are not enterprise SSO identities.

Use HTTPS for shared hosting. Loopback HTTP is an explicit development exception. Never include real API keys, cookies, connection URLs or review notes in a public reproduction. Use isolated synthetic organizations and the test database configuration. The API's append-only history does not protect against trusted database administrators; deployments must supply backup, retention and administrator controls.
