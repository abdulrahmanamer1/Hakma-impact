# AHVT V42 — Final Audit Pass

## Changes
- Corrected the permission-switch behavior: when granular permissions are disabled, active ADMIN accounts retain normal administrative access; CREATOR remains unrestricted.
- When granular permissions are enabled, the existing role-permission matrix remains authoritative.
- Kept public certificate verification limited to certificate data and never exposed internal IDs, tokens, or edit controls.
- Kept public cards read-only; printing remains an administrative action.
- Rechecked presence of the major systems: certificates, cards, QR scanner, chat, academy, backup/restore, live room, podcast, reports, permissions, equipment, attendance, tasks, initiatives, events, honor, media, and public search.
- Re-ran Python syntax validation successfully.

## Important validation boundary
Browser camera permissions, HTTPS behavior, WebRTC across separate devices/networks, and production upload persistence require a real deployed browser environment. Static/source validation alone cannot prove those runtime conditions.
