# AHVT V52 — Final Public UI / Settings Fixes

## 1. Public vs Administration controls
- Public visitors no longer see edit/delete controls on committee or member cards.
- Committee public cards show committee name, responsibilities/description, responsible person, and member count.
- Member public cards are single clickable squares; tapping the card opens the member profile.
- Administrative controls remain available only to authenticated administrators.

## 2. Member deletion
- Added a direct delete button to the member profile for administrators.
- Deletion uses the existing POST endpoint with no confirmation dialog, as requested.

## 3. Settings persistence
- Appearance saves no longer erase uploaded Hero/public background or video assets.
- Public-control settings no longer overwrite fields that are not present in the form.

## 4. About / AHVT content
- About page now presents team name, slogan, description, vision, mission, and goals clearly.
- Added an About AHVT section to the public homepage so saved team information is not isolated to the About page.

## 5. Cinematic space theme
- Public pages now use a dark space background with stars and subtle planet/glow effects.
- Public cards, news, initiatives, committees, and information panels use the same blue cinematic visual language.

## 6. News and member presentation
- Public news cards are compact and blue rather than white.
- Member list is compact and responsive, with square cards and click-to-view behavior.
