# CBSUA Helpdesk UI styling

This document records the CBSUA identity and the follow-up component-level
polish for the agent desk and Studio customer portal.

## Design constraints

- Product UI prioritizes clarity and predictable interaction over decoration.
- Follow the repository's frontend guidance: use Frappe UI semantic tokens,
  Tailwind utilities, responsive layouts, and neutral gray shades.
- The CBSUA logo and favicon carry the institution's identity. Do not tint,
  crop, or recreate the official mark with CSS.
- Keep ticket status, priority, SLA, and validation colors meaningful to their
  existing domain semantics; do not reuse them as general brand decoration.
- Preserve existing configuration overrides and all ticket/portal behavior.

## Identity and first styling pass

### Agent desk

- `BrandLogo.vue` uses the configured CBSUA mark and a neutral, contained
  frame. The image itself remains uncropped.
- `UserMenu.vue` keeps the brand name visually distinct from the signed-in
  user's name, using the neutral high-emphasis text token.
- `AppSidebar.vue` uses compact, subdued section labels so navigation groups
  are visually subordinate to their actionable items.
- The existing collapse, section expansion, profile menu, and navigation
  behavior are unchanged.

### Customer portal

- `PortalNavMenu.vue` always renders the CBSUA logo fallback when no
  administrator-provided logo exists. The image uses a neutral contained frame;
  the brand name uses the same high-emphasis neutral text as the desk.
- `PortalEmptyState.vue` has a consistent icon field, a clearer title/
  description hierarchy, and more readable supporting copy.
- `PortalSidebarSection.vue` provides a visible hover state and keyboard
  focus ring for collapsible ticket-detail sections. The existing collapse
  lifecycle is retained so child animations can replay.
- `PortalStatusPill.vue` improves label emphasis while retaining the status
  dot's configured semantic color.
- `NewTicketForm.vue` gives the description editor a persistent, readable
  label rather than relying on placeholder text.

### Browser shell

- The desk's Safari pinned-tab mask icon points to the CBSUA favicon asset.
- Desk and portal application names, favicon defaults, and PWA icons are
  documented in [CBSUA branding](cbsua-branding.md).

## Token choices

| Purpose | Token |
| --- | --- |
| Logo backing surface | `surface-gray-1` |
| Logo outline | `outline-gray-2` |
| Brand-name and empty-state title | `ink-gray-9` |
| Supporting text | `ink-gray-6` |
| Focus outline | `outline-gray-3` |

Use semantic Frappe UI tokens rather than arbitrary hex values in individual
components. Preserve domain-specific colors for ticket status, priority, SLA,
and validation states.

## Intentionally deferred

- Global primary button and link colors.
- Dashboard charts and status colors.
- Portal hero/banner artwork and colors.
- Ticket priority and status palette changes.
- Typography and font loading.
- Full navigation and page-layout redesign.
- Custom dark-mode palette.

These require an approved CBSUA design-system reference and screenshot-based
review. Do not infer exact brand color values solely from a compressed logo.

## Verification checklist

- [ ] Desk brand mark is legible in expanded and collapsed sidebar states.
- [ ] Desk brand mark remains legible in light and dark modes.
- [ ] Sidebar section labels remain distinguishable from navigation items.
- [ ] Portal logo is visible for guests, customers, and agents.
- [ ] Portal fallback works when `HD Settings.brand_logo` is empty.
- [ ] A configured logo still overrides the CBSUA default.
- [ ] Empty states read clearly at mobile and desktop widths.
- [ ] Portal section controls expose visible keyboard focus.
- [ ] Status colors remain driven by configured ticket status metadata.
- [ ] New-ticket description label remains visible when the editor is empty.
- [ ] Mobile header and sidebar do not overflow.

## Implementation notes

The modified Vue components include short inline comments where a styling
choice or lifecycle constraint is not self-evident. The portal is a Studio
standard app: page/component source lives in `studio/helpdesk/` and is built
through the Studio workflow documented in `studio/README.md`. Shared desk and
portal components should stay in `shared/src` when both frontends need the
same behavior.
