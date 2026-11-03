# CI cleanup notes

This branch intentionally keeps `USER_AUTH_MODE=disabled` as the public product mode and preserves fail-closed behavior for an unconfigured provider mode.

The CI security gate now blocks on production dependency vulnerabilities via `npm audit --omit=dev --audit-level=moderate`. Development-tooling advisories are still reported in CI but do not incorrectly classify the deployed application as vulnerable.

Current dev-tooling advisories should still be upgraded in a follow-up lockfile refresh when a package-manager execution environment is available; do not use `npm audit fix --force` blindly.
