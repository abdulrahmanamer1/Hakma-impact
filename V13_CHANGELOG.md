# AHVT V13 — OWNER CINEMATIC EDITION

## Included
- Admin sidebar fixed to the LEFT on desktop and mobile drawer opens from the left.
- Member and administrator photo uploads; new images are stored as JPG.
- Member fields: department, stage, membership number, card issue/expiry, NFC UID.
- Administrator fields: department, card issue/expiry, membership number, NFC UID.
- Landscape certificate studio with editable issuer, title, intro, full body, footer, note, three logo slots, add/remove logo, QR verification, revoke and reissue.
- Three landscape certificate templates: Classic, Minimal, Impact.
- Direct map picker for initiatives: click the map or drag the marker; latitude/longitude are hidden implementation fields.
- Up to three simultaneous internal live rooms.
- Live room front/back camera switching, microphone/camera controls, viewer count, and per-room share action.
- Per-live channel/location label so different admins can operate separate live stations.
- Multi-file media uploads for news, initiatives, events, partners and the central media center.
- Uploaded raster images are converted to JPG; videos are stored as uploaded video files.
- Member/admin printable cards with photo, name, department, role, committee/admin unit, validity, QR, and NFC-ready URL; Web NFC writing is offered where the browser supports it.
- Cinematic dark visual system with white text on blue backgrounds and subtle star field.
- Persistent owner credentials remain stable across restarts; owner password is the value configured in `HIKMA_OWNER_PASSWORD` or the built-in owner default requested for this release.
- Backup export/import includes the new attachments table.

## External live platforms
Sharing a room link to Instagram/Facebook/YouTube is supported. Direct simultaneous RTMP publishing to those platforms requires the platform's API/RTMP credentials and a suitable streaming relay/TURN infrastructure; this release does not fake that capability.
