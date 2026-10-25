# AHVT V30 — Core completion pass

- Unified public news cover images through `asset_url()`.
- Added global image error fallback to the AHVT placeholder instead of broken-image icons.
- Added lazy loading and async decoding for images that do not explicitly define them.
- Kept persistent upload serving under `/uploads/<path:filename>`.
- Full backup manifest version updated to V30.
- Existing V29 persistent upload, asset URL, and reorder foundations retained.

## Validation
- Python syntax compilation: PASS.
- Template scan: public news cover images no longer bypass `asset_url()`.
