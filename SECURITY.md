# Security Policy

SkillForge is a **local-first** tool. It runs entirely on your machine, binds
to `127.0.0.1`, and never sends your data to any server other than the AI
provider you configure. This document explains the threat model and how to
report vulnerabilities.

## Threat model

SkillForge assumes a **single-user, local machine** context. The primary
threat is **browser-driven attacks** (CSRF / DNS rebinding) against the local
API server — not network attackers, since the server binds to loopback only.

### What protects you

| Layer | Mechanism |
|---|---|
| **Network bind** | Defaults to `127.0.0.1` (loopback only). Not reachable from the network unless you explicitly set `SKILLFORGE_API_HOST=0.0.0.0`. |
| **Local-origin guard** | `LocalOriginGuardMiddleware` rejects any browser request whose `Origin` or `Referer` header names a non-loopback host. A malicious website (`evil.com`) cannot drive the local API. Requests without an Origin header (curl, the CLI) are allowed. |
| **Pairing flow** | Marketplace pairing uses a 6-char CSPRNG code (single-use, 10-min TTL). Bridge tokens are 256-bit, stored only as SHA-256 hashes, returned once, and revocable. Token comparison is constant-time (`hmac.compare_digest`). |
| **Rate limiting** | Pairing endpoints (`/pair/code`, `/pair/complete`) are capped at 10 attempts/min per client, making brute-force of the code space (~887M) provably infeasible. |
| **CORS** | Explicit allowlist (localhost dev server + same-origin). Never `*` + credentials. |
| **Path traversal** | Install, validate, and preview endpoints reject paths that escape the skills directory. |
| **No auto-execution** | Generated tool scripts are NEVER executed automatically. The tool executor requires explicit `confirm=True`, an allowlist match, and a 30s timeout. |

### What is NOT protected against

- **Anyone with local access to your machine** can call the API (it's
  loopback-bound with no auth — that's by design for a local-first tool).
- **Malicious skills** you choose to install. SkillForge validates structure
  but does not sandbox or audit skill content. Review SKILL.md before
  installing community skills.

## Reporting a vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

Email: `security@skillforge.dev` (or open a private security advisory via
GitHub's "Security" → "Advisories" → "Report a vulnerability").

Please include:
- A description of the issue and its impact
- Steps to reproduce (proof of concept)
- The SkillForge version (run `skillforge --version`)

We will acknowledge within 48 hours and aim to publish a fix within 7 days
for high-severity issues.

## Disclosure policy

- We follow **coordinated disclosure**: we'll credit reporters in the release
  notes unless you prefer to remain anonymous.
- A CVE will be requested for confirmed high/critical vulnerabilities.
- Fixed releases are tagged and the GitHub Release notes describe the fix.

## Dependency security

SkillForge is distributed as a single PyInstaller binary that bundles its
Python dependencies. Before each release:
- `pip-audit` is run against the dependency tree
- The lockfile and binary are rebuilt from a clean environment

If you find a vulnerability in a bundled dependency, report it upstream AND to
us so we can ship a patched binary promptly.
