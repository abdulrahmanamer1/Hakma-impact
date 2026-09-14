# AHVT V27 FINAL — Final Product Specification

## Public UI
- Dark/Cinematic theme.
- Left-side navigation; mobile drawer opens from the left.
- Scroll-down/dynamic landing-page sections.
- Remove the old loading wheel.
- Animated statistic cards: beneficiaries, administrators, members, temporary volunteers,
  volunteer hours, initiatives, news.
- Initiatives card is blue.
- Remove "Our Impact in Numbers" as a standalone navigation item; surface its useful
  metrics on the landing page.
- Add landing-page search.
- Keep AHVT Assistant in navigation.
- Navigation order begins: Administrators, Members, Temporary Volunteers.

## Administration
- Administration page must load.
- "About the Team" is editable from administration.
- Every editable setting has a real Save action and persists.
- Identity/logo/image settings persist across restarts when persistent storage is configured.
- Administrators can reorder administrator/member/temporary-volunteer cards, with
  position-based ordering.

## Uploads
- Direct uploads for images/video/files; no URL-only requirement.
- Uploaded media must be stored, served, and remain available after restart with
  persistent storage.
- Multi-image/multi-video support where specified.
- Fix broken image/404/question-mark media rendering.

## QR / Camera
- Camera opens from the user's phone through the site.
- Primary broadcast camera works without requiring pre-approved secondary sources.
- QR scanning supports attendance, tasks, events, equipment receiving/returning.
- QR identifies member/administrator automatically and records date/time.
- Manual entry remains available if a card is lost.
- Camera UI provides clear ready/waiting/denied/unavailable states and a manual fallback.
- HTTPS and browser permissions are handled with useful user-facing guidance.

## Equipment
- Receiver can scan the member/administrator electronic-card QR.
- Receiver/returner workflow records person, item, operation, date and time.
- Manual workflow remains available.

## Live / Multi-source Broadcast
- A live stream can start immediately from the current device camera.
- Secondary phones/cameras can request to join.
- Owner/admin can accept/reject source requests.
- Up to 6 sources per live room.
- Front/rear camera switching, microphone/camera controls.
- Multiple source angles are combined into one live room.
- External embeddable sources/links can be hosted when the source platform permits embedding.
- Multiple external links/sources can be attached.
- Live title, description, event location, date/time and viewer count.
- Record and save live sessions.

## Certificates
- Separate Certificate Studio.
- A4 landscape.
- Beneficiary name alone is sufficient to create a test certificate.
- Certificate number is generated automatically and displayed.
- QR is generated and displayed for verification.
- Author name instead of issuer name.
- All text editable.
- Font, size, colors and logos editable.
- Add/remove/replace logos.
- Save templates.
- Preview before printing.
- Edit/delete certificates according to permissions.
- Creation must save the record before verification/QR generation; no false
  "certificate not found" or "unable to save" error on a valid minimal submission.

## Electronic Cards
- Separate administration/owner card studio.
- Blue or user-selected color.
- User-selected design, font, logo and physical size.
- Save template button.
- Print-preview button.
- Public/private visibility can be selected by owner/admin.
- End users cannot print cards; authorized owner/admin can.

## Honor List
- Public "Honor List" section.
- Cinematic profile pages.
- Main image plus multiple additional images, Instagram-like gallery.
- Recognition type, reason, achievement, date, event, committee/department, badge,
  linked certificate.
- Add/edit/delete according to permissions.

## Academy
- Direct upload of images/video/files rather than URL-only media.

## Maps
- Tasks, events, initiatives and similar location-bearing content use direct map
  point selection, while retaining an optional textual place field.

## Reports
- Comprehensive PDF export.
- Include members, administrators, temporary volunteers, hours, attendance, tasks,
  initiatives, events, news, courses, equipment, certificates and statistics.
- Compact layout/minimal paper usage.
- Blue branded header bar and polished visual design.
- Avoid Internal Server Error; provide graceful error handling/fallback.

## Settings / Permissions / Backup
- Permission system can be enabled from Settings.
- Backup includes database and uploaded media.
- All lists have edit/delete actions according to permissions.
- Delete requires confirmation.
- Remove the notifications section to reduce load.

## Messaging
- Private one-to-one conversations.
- Other users cannot view another private chat.
- Edit/delete messages and support reactions/likes.

## Paid content
- Courses/services can be Free or Paid.
- Paid price in IQD.
- Payment information visible to subscriber.
- Subscriber uploads payment receipt/screenshot.
- Owner/admin receives and reviews receipt.
- Subscriber is clearly warned to upload the receipt and wait for review.

## Instagram
- Team Instagram: https://www.instagram.com/hikma.ahvt/
