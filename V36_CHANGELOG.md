# AHVT V36

## Permission and certificate/card hardening
- Granular permissions disabled mode no longer silently grants every ADMIN account full access; SUPER_ADMIN remains the delegated role and CREATOR remains unrestricted.
- Public certificate verification now exposes only verification-safe certificate fields and never internal IDs/tokens.
- Certificate verification remains available before login and returns an invalid/empty certificate to the existing verification template rather than exposing internals.
- Card template preview now supports temporary-volunteer card templates in addition to member/admin templates.
- Preserved permanent uploads, image fallback handling, QR generation, and previous V35 backup/restore behavior.
