# HIKMA IMPACT V14 — FINAL OWNER CINEMATIC

## Included
- Left-side administration navigation and left-side public drawer.
- Fully dark/cinematic visual system with animated star field; map remains normal for usability.
- Cinematic member gallery and public member profile pages.
- Member/administrator photo upload converted to JPG.
- Department + stage fields for members.
- Independent Team Cards Studio for owners/admins.
- Custom card size, colors, fonts, logo upload, field visibility, QR and NFC UID.
- Public/private card visibility controlled by administration.
- Only administration has the official print endpoint; public cards hide print controls and print media.
- NFC Web API write button where the browser/device supports it.
- A4 landscape cinematic certificates with editable text, writer name, labels, colors, fonts, 3 logos, QR verification, revoke/reissue.
- Optional task map with draggable marker; no manual latitude/longitude entry required.
- Up to 6 simultaneous live rooms.
- Up to 6 camera/mobile source peers per live room.
- Front/rear camera switching and device selection.
- Secondary mobile/camera source mode with labels.
- Live recording archive upload for each local source when supported by MediaRecorder.
- Podcast public section and left navigation entry.
- Podcast control room: shows, seasons, episodes, guests, hosts, directors, producers, audio/video, transcripts, clips and equipment checklist.
- Multi-file media uploads retained; images are converted to JPG.
- Backup/export includes the new card and podcast tables.
- Owner account retains the existing owner email and owner password environment override; default owner password is the value configured in the project.

## Deployment
Upload the ZIP to the existing Render service. Do not delete the existing service or persistent disk. Deploy the latest upload on the same service so the existing database remains attached.
