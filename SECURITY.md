# Security Policy

## Supported version

Security fixes are applied to the latest version on the default branch. The frozen AMind v1 evidence release remains immutable unless a new, explicitly versioned release supersedes it.

## Report a vulnerability privately

Please use [GitHub private vulnerability reporting](https://github.com/lc708/AMind/security/advisories/new). Do not open a public issue for a vulnerability.

Include:

- the affected file, command, or installation flow;
- impact and a minimal reproduction;
- whether the issue can modify files, execute code, leak data, or bypass an evidence boundary;
- any proposed mitigation, if known.

Please do not include real secrets, private Anthropic information, or sensitive third-party data in a report.

## Scope

Security reports may cover the installable Skill, its Python query and verification tools, manifest/path validation, build scripts, or instructions that could cause unsafe agent behavior.

Evidence accuracy, attribution, and version-boundary problems are important, but they are normally handled through the public evidence-correction issue form unless disclosure itself would create a security or privacy risk.
