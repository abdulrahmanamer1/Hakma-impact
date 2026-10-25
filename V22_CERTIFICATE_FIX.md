AHVT V22 Certificate Fix

- Fixed certificate creation flow so it no longer redirects to a missing certificate after successful creation.
- Certificate is read back from SQLite immediately after commit before display.
- Certificate view accepts only certificate ID or certificate number; recipient names are no longer treated as certificate IDs.
- Added certificate deletion with QR cleanup and confirmation.
- Kept A4 landscape, editable text, writer name, logos, colors, fonts and QR verification.
