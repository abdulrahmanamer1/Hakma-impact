# Hikma Plus V44 — production hardening notes

## Application changes
- Added `/healthz` and database-aware `/readyz` endpoints.
- Added secure cookie defaults, baseline browser security headers, same-origin checks on browser writes, and reverse-proxy support for trusted TLS termination.
- Added persistent, database-backed login failure throttling (eight failures in a 15-minute window triggers a 15-minute cooldown).
- Added authenticated task-attachment downloads and conversation-member-only chat media delivery; generic `/uploads/...` no longer serves `task-*` or `chat-*` files.
- Added explicit `backup` permission checks to JSON backup export/import.
- Hardened full ZIP backup restore against traversal paths, Windows-style path separators, duplicate archive entries, symlinks, unexpected archive members, oversized expansion, and invalid SQLite databases.
- Added new collaboration tables to JSON backup/restore coverage.
- Added Render Blueprint, Gunicorn Procfile, Dockerfile, environment example, and smoke-test suites.

## Validation
- Python syntax, all HTML templates, and all JavaScript files passed static checks.
- Six backup archive safety unit tests passed in the build environment.
- Flask integration tests are included but were not run because Flask/Werkzeug are unavailable in this build environment and package downloads are blocked.
- Deployment-specific behavior still requires a staging deployment with HTTPS, persistent disk, secrets, and real WebRTC clients.
