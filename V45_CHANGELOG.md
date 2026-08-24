# AHVT V45 — Electronic Identity QR

- Members and temporary volunteers now have a stable identity QR embedded in their electronic ID cards.
- The QR resolves to `/scan/<kind>/<record_id>` and therefore identifies the person type and ID for attendance, tasks, events and equipment.
- QR files use stable per-person filenames and are stored under the persistent uploads directory.
- Member and temporary volunteer cards both display the identity QR explicitly.
- Existing administrator QR behavior remains supported.
- Python syntax check passed.
