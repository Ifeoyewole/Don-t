---
name: Field Utility System
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#44474d'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#75777e'
  outline-variant: '#c5c6ce'
  surface-tint: '#4f5e7e'
  primary: '#041632'
  on-primary: '#ffffff'
  primary-container: '#1b2b48'
  on-primary-container: '#8393b5'
  inverse-primary: '#b7c7eb'
  secondary: '#0051d5'
  on-secondary: '#ffffff'
  secondary-container: '#316bf3'
  on-secondary-container: '#fefcff'
  tertiary: '#211500'
  on-tertiary: '#ffffff'
  tertiary-container: '#3b2800'
  on-tertiary-container: '#ac8e5b'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d7e2ff'
  primary-fixed-dim: '#b7c7eb'
  on-primary-fixed: '#091b37'
  on-primary-fixed-variant: '#374765'
  secondary-fixed: '#dbe1ff'
  secondary-fixed-dim: '#b4c5ff'
  on-secondary-fixed: '#00174b'
  on-secondary-fixed-variant: '#003ea8'
  tertiary-fixed: '#ffdea7'
  tertiary-fixed-dim: '#e3c28a'
  on-tertiary-fixed: '#271900'
  on-tertiary-fixed-variant: '#594317'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
  status-label:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 18px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  gutter-mobile: 16px
  gutter-desktop: 24px
  margin-edge: 20px
  touch-target-min: 48px
---

## Brand & Style
The design system is engineered for high-stakes site inspections where clarity, speed, and reliability are paramount. The visual language adopts a **Corporate / Modern** aesthetic with a heavy emphasis on utility and legibility, mirroring the precision of civil engineering.

The brand personality is professional, authoritative, and dependable. It avoids superfluous decoration in favor of a "rugged-digital" look—clean lines, generous touch targets for field use, and a strict information hierarchy. The interface must remain functional under varying outdoor lighting conditions, prioritizing high-contrast ratios and clear semantic signaling to evoke a sense of structural integrity and safety compliance.

## Colors
The palette is rooted in a deep "Structural Navy" to establish professional authority. The primary action color is a vibrant "Professional Blue," ensuring that interactive elements are immediately identifiable against neutral data displays.

Semantic colors (Green, Amber, Red) are treated with high saturation to ensure critical status updates—such as inspection passes or failures—are unmistakable even at a glance or in bright sunlight. The background uses a cool, light gray to reduce glare, while pure white is reserved for cards and containers to create a clear "layer of data" above the workspace.

## Typography
**Inter** is the foundational typeface for this design system, chosen for its exceptional legibility and systematic, utilitarian feel. The type scale is optimized for form-heavy workflows, using a robust weight ladder to distinguish between section headers, field labels, and user input.

In field conditions, larger body text (16px) is the standard to ensure readability on handheld devices. All labels for data entry use high-contrast weights and occasional uppercase styling to separate them visually from the dynamic data they describe.

## Layout & Spacing
The layout follows a **Fluid Grid** model designed primarily for tablet and mobile PWA usage. It utilizes an 8px base unit for all rhythmic spacing, ensuring a consistent vertical cadence.

- **Mobile/Handheld:** A single-column layout with 16px side margins to maximize screen real estate for form fields and photo evidence.
- **Tablet/Desktop:** A 12-column grid that allows for "Master-Detail" views, where an inspection list persists on the left while specific joint details are edited on the right.
- **Touch Targets:** All interactive elements maintain a minimum 48px height to accommodate gloved or weathered hands in a construction environment.

## Elevation & Depth
Depth is used sparingly and functionally. This design system employs **Tonal Layers** and **Ambient Shadows** to define the workspace:

1.  **Level 0 (Canvas):** The `#F8FAFC` background representing the base environment.
2.  **Level 1 (Cards/Containers):** White surfaces with a very soft, diffused shadow (0px 2px 4px, 5% opacity navy) to distinguish individual inspection items or form sections.
3.  **Level 2 (Modals/Pickers):** More pronounced shadows (0px 8px 16px, 10% opacity navy) used for high-priority overlays, such as signature pads or camera interfaces.

This layered approach ensures that the user understands the "stack" of information without the UI feeling overly "app-like" or decorative.

## Shapes
The shape language is defined by a "Soft Engineering" approach. A **Level 2 (Rounded)** setting is applied across the system.

- **Standard Elements:** Input fields, buttons, and checkboxes use a 0.5rem (8px) radius, providing a professional look that is easier on the eyes than sharp corners while maintaining a structured feel.
- **Card Containers:** Larger elements like inspection summary cards utilize a 1rem (16px) radius to create clear visual grouping.
- **Status Pills:** Semantic indicators (Pass/Fail) use a fully rounded "pill" shape to distinguish them from interactive buttons.

## Components
- **Buttons:** Primary buttons use the Professional Blue (#2563EB) with white text. Secondary buttons use a Navy outline. All buttons must have a height of 48px-56px for field accessibility.
- **Inspection Chips:** Small, high-contrast badges for status. "Pass" uses a green background with dark green text; "Fail" uses red background with dark red text. These are non-interactive indicators.
- **Input Fields:** Thick 2px borders when focused using the Secondary Blue. Large, clear labels placed above the field (never inside as placeholders) to ensure context is never lost during data entry.
- **Checklists:** Large tap areas for joint inspection points. Successful checks should trigger a subtle green haptic/visual feedback.
- **Cards:** Used to wrap inspection segments (e.g., "Joint Integrity," "Material Quality"). Each card should have a clear header and a summary status icon.
- **Offline Indicator:** A persistent, low-profile bar at the top of the viewport indicating sync status (e.g., "Offline - Changes Cached" or "Online - Synced").