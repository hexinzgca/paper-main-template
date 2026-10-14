# Security and sensitive information

Do not commit access tokens, private keys, unpublished sensitive data, temporary
signed URLs, or private reviewer information. `.gitignore` is not a secret scanner.
Report security-sensitive issues through the maintainers' private channel once one
has been configured; do not publish live credentials in an Issue or PR.

This template configures no private contact, organization identity, or credential.
Maintainership must add the actual disclosure route before public release.
CI uses read-only permissions and does not execute fork PRs with project secrets.
