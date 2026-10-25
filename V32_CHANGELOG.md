# AHVT V32 — QR / Camera / Attendance / Tasks / Equipment

- Improved QR scanner UX with explicit camera states (ready, denied, unavailable/HTTPS).
- Added front/back camera switching.
- Added manual QR input fallback when camera is unavailable.
- Kept automatic member identification, timestamping, attendance check-in/out, task completion, and equipment checkout/return flows.
- Preserved permanent image/asset handling from V29/V30 and temporary-volunteer card support from V31.
- Python syntax validation passed with `python -m py_compile app.py`.
