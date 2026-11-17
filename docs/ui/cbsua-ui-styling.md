# CBSUA Helpdesk UI styling

This document records the initial styling pass applied after the CBSUA asset and
application-identity integration.

## Styling intent

The first pass is deliberately restrained. It introduces a small institutional
green accent in the two persistent brand touchpoints while retaining Frappe UI's
existing neutral surfaces, spacing, controls, and light/dark behavior.

The CBSUA seal is the primary source of institutional identity. Its green and
yellow/gold visual language informs the accent direction; this pass uses
Frappe's semantic green tokens rather than introducing unverified custom hex
values or replacing the framework's color system.

## Implemented touchpoints

### Agent desk

- The shared `BrandLogo.vue` mark now sits on a subtle semantic green surface,
  with a thin semantic green outline and circular crop.
- The application name in `UserMenu.vue` uses the semantic green text token.
- Existing user-menu layout, collapse behavior, and menu interactions are
  unchanged.

### Customer portal

- `PortalNavMenu.vue` always renders the CBSUA logo fallback when no
  administrator-provided brand logo exists. Previously the empty-logo branch
  rendered a blank spacer, so the fallback path is now explicit.
- The logo uses the same restrained green surface and outline treatment.
- The portal brand name uses the same semantic green text token.
- Existing route-dependent title visibility and dropdown behavior are retained.

### Browser shell

- The desk's Safari pinned-tab mask icon now points to the CBSUA favicon asset
  rather than the previous Frappe Helpdesk manifest image.

## Token choices

| Purpose | Token |
| --- | --- |
| Logo backing surface | `surface-green-1` |
| Logo outline | `outline-green-2` |
| Brand-name text | `ink-green-7` |

These are Frappe UI semantic tokens. Do not replace them with arbitrary hex
values in individual components. If a formal CBSUA theme is introduced later,
centralize its palette and semantic mappings, then test contrast in both themes.

## Deliberately deferred

- Global primary button and link colors.
- Dashboard charts and status colors.
- Portal hero/banner colors.
- Ticket priority and status palette.
- Typography and font loading.
- Full navigation and page-layout redesign.
- Custom dark-mode palette.

These need an approved design-system reference and screenshot-based review.
Do not infer exact brand color values solely from a compressed logo export.

## Review checklist

- [ ] Desk brand mark is legible in expanded and collapsed sidebar states.
- [ ] Desk brand mark remains legible in light and dark modes.
- [ ] Portal logo is visible for guests, customers, and agents.
- [ ] Portal fallback works when `HD Settings.brand_logo` is empty.
- [ ] A configured logo still overrides the CBSUA default.
- [ ] Brand-name contrast remains accessible in both themes.
- [ ] Mobile header and sidebar do not overflow.
