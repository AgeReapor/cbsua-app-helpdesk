# CBSUA Helpdesk branding

This document records the first institutional-branding integration for the
agent desk and the Studio customer portal.

## Scope

- Apply the CBSUA logo to the agent desk's shared brand mark.
- Apply the same logo to the customer portal header.
- Provide a CBSUA application name when no custom Helpdesk brand name is set.
- Use the CBSUA favicon for both applications when no site-level favicon is set.
- Use CBSUA artwork in the installable desk application's manifest.
- Preserve existing `HD Settings` and `Website Settings` overrides.

This is an identity integration plus a restrained first styling pass. The
institutional accent treatment is documented in
[CBSUA UI styling](cbsua-ui-styling.md). A complete visual redesign remains
a separate follow-up.

## Source assets

The original image files remain in `desk/src/assets/logos/`:

| File | Intended use |
| --- | --- |
| `cbsua-logo-2400.png` | Primary CBSUA brand mark |
| `android-chrome-192x192.png` | PWA icon, 192 px |
| `android-chrome-512x512.png` | PWA icon, 512 px |
| `apple-touch-icon.png` | Apple home-screen icon |
| `HDLogo.vue` | Legacy Helpdesk mark; retained for compatibility |

The favicon set is stored in `desk/public/cbsua/`:

- `favicon.ico`
- `favicon-16x16.png`
- `favicon-32x32.png`

The portal and API use stable public paths under
`/assets/helpdesk/desk/cbsua/`. The source logo is imported by the desk through
Vite; the portal uses the static asset URL because Studio is built separately
from the desk's Vite module graph.

## Branding precedence

### Name

1. `HD Settings.brand_name`
2. `CBSUA Helpdesk`

The backend boot context and `helpdesk.api.config.get_config` use the same
fallback so the portal title and both frontends agree.

### Logo

1. `HD Settings.brand_logo`
2. `/assets/helpdesk/desk/cbsua/cbsua-logo-2400.png`

The desk imports the source PNG through Vite. The API returns a stable public
URL for the portal and other clients.

### Favicon

1. `HD Settings.favicon`
2. `Website Settings.favicon`
3. `/assets/helpdesk/desk/cbsua/favicon.ico`

The Frappe app launcher uses the 32 px CBSUA favicon. The desk's HTML shell
declares 16 px, 32 px, ICO, and Apple touch icon assets.

## Frontend integration points

- `desk/src/components/BrandLogo.vue`: shared agent-desk brand mark.
- `desk/src/stores/config.ts`: desk name, logo, and favicon defaults.
- `desk/src/components/layouts/Sidebar.vue`: Help modal logo and product title.
- `studio/helpdesk/components/header/PortalNavMenu.vue`: customer portal brand mark.
- `studio/helpdesk/stores/session.ts`: portal fallback name and logo.
- `desk/index.html`: static browser and Apple home-screen metadata.
- `desk/vite.config.js`: PWA manifest name, description, and icon sources.

## Backend integration points

- `helpdesk/api/config.py`: shared name, logo, and favicon defaults returned by
  the existing configuration endpoint.
- `helpdesk/helpdesk/hooks/studio_app.py`: portal document title fallback.
- `helpdesk/hooks.py`: app metadata and Frappe app-launcher logo.

No database migration or new DocType is required. Existing administrator-set
branding remains authoritative.

## Build and verification

From the Helpdesk app directory:

```bash
cd desk
yarn build
```

Then build the standard Studio portal using the existing workflow:

```bash
bench build-studio-app helpdesk --site <site>
```

Verify:

1. `/helpdesk` displays the CBSUA logo in the desk user menu and Help modal.
2. `/help` displays the same logo and name in the portal header.
3. Both applications use the CBSUA favicon.
4. The PWA manifest returns CBSUA name and icon paths.
5. Configured `HD Settings.brand_name`, `brand_logo`, and `favicon` override
   the defaults.
6. `Website Settings.favicon` remains the secondary favicon override.
7. Guest, customer, and agent portal sessions receive the same public branding.

A source commit does not prove these runtime checks. Run them in a bench
environment after building both frontends.

## Follow-up styling

The next UI change should establish and apply CBSUA design tokens to the desk
and Studio portal. Use the approved institutional design-system reference for
exact colors and typography instead of inferring a palette from the logo image.
Keep Frappe UI semantic token conventions and test light and dark themes.
