# Design System Documentation: The Ethereal Arbiter

## 1. Overview & Creative North Star

### The Creative North Star: "The Ethereal Arbiter"
This design system is built to transform the dense, opaque world of legal jargon into a space of absolute clarity and breath. It rejects the traditional "legal" aesthetic of heavy borders and cramped grids, opting instead for **The Ethereal Arbiter**—a visual language that is brutally minimal, clinical in its precision, yet organic in its feel.

We break the "template" look by utilizing intentional asymmetry and expansive negative space. The UI should feel like a series of high-end editorial plates floating in a light-filled gallery. By leveraging extreme typography scales and "glass" surfaces, we guide the user’s eye toward what matters: the demystified truth of their documents.

---

## 2. Colors

The palette is anchored in high-contrast neutrals and a deep, authoritative teal. It is designed to feel "expensive"—achieved through subtle shifts in tone rather than heavy-handed decoration.

### The Color Tokens
- **Background**: `surface` (`#F8F9FA`)
- **Primary / Accent**: `primary` (`#004541`) / `primary_container` (`#115E59`)
- **Text**: `on_surface` (`#111827`)
- **Risk Semantics**: 
  - **High**: `error` (`#9F1239`)
  - **Warning**: `secondary_container` / Custom Amber (`#B45309`)
  - **Safe**: `tertiary` (`#166534`)

### The "No-Line" Rule
**Explicit Instruction:** Do not use 1px solid borders for sectioning or containment. Boundaries must be defined solely through background color shifts. For example, a `surface_container_low` section sitting on a `surface` background creates a clear but soft boundary. 

### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers. We use the Material surface tiers to define depth:
1.  **Base Canvas**: `surface` (`#F8F9FA`) with faint, diffused radial gradients.
2.  **Primary Containers**: `surface_container_lowest` (`#FFFFFF`) for the main glass panels.
3.  **Nested Content**: Use `surface_container` or `surface_container_high` for internal modules (like a "Summary" box inside a larger panel).

### The "Glass & Gradient" Rule
To achieve "Ethereal Glassmorphism," use semi-transparent white backgrounds (`rgba(255, 255, 255, 0.7)`) combined with a `backdrop-blur: 20px`. Main CTAs and Hero sections should utilize subtle gradients transitioning from `primary` to `primary_container` to provide a sense of "visual soul" and depth.

---

## 3. Typography

The typography strategy relies on the tension between a heavy, geometric display face and a highly legible, elegant body face.

### Font Pairings
- **Headings (Display/Headline)**: **Plus Jakarta Sans** (Mapping to Satoshi/Outfit). Use "Tight" tracking (-2% to -4%) and "Bold/Heavy" weights.
- **Body & Metadata**: **Manrope** (Mapping to DM Sans). Use "Normal" tracking and "Regular/Medium" weights.

### Hierarchy
- **Display-LG/MD**: Reserved for hero demystification headers. This is the "voice" of the system—authoritative and large.
- **Title-LG/MD**: Used for document section titles.
- **Body-LG**: The primary reading size for legal summaries.
- **Label-SM**: Used for metadata and risk tags. All-caps for labels is permitted only if letter-spacing is increased by 5%.

---

## 4. Elevation & Depth

We avoid the "card-on-gray" cliché by focusing on **Tonal Layering**.

### The Layering Principle
Depth is achieved by "stacking" surface tiers. A `surface_container_lowest` panel on a `surface` background creates a natural lift. For NyayaMitra, the main document panels should feel like they are floating 20px above the canvas.

### Ambient Shadows
When a floating effect is required (e.g., the primary document view), use the following "Ambient Shadow":
`box-shadow: 0 20px 40px rgba(17, 24, 39, 0.03);`
*Note: The shadow uses a 3% opacity of the `on_surface` charcoal, not pure black, to mimic natural light.*

### The "Ghost Border" Fallback
If an edge must be defined (e.g., for accessibility), use a **Ghost Border**:
- **Stroke**: `outline_variant` at 15% opacity.
- **Style**: Solid, 1px.
*100% opaque borders are strictly forbidden.*

---

## 5. Components

### Buttons
- **Primary**: Pill-shaped (`rounded-full`), `primary` background, `on_primary` text. Use a subtle inner-glow for a "glass" button effect.
- **Tertiary**: Ghost style. No background, no border. Only text with a leading icon.

### Chips (Risk Indicators)
- **High Risk**: `error_container` background with `on_error_container` text.
- **Safe**: `tertiary_fixed` background with `on_tertiary_fixed_variant` text.
- **Styling**: `sm` (0.25rem) roundedness to maintain a "clinical" sharp-edge look compared to the pill-shaped buttons.

### Cards & Document Panels
- **Container**: `surface_container_lowest` (#FFFFFF).
- **Corner Radius**: `xl` (1.5rem) for main panels; `lg` (1.0rem) for internal cards.
- **Separation**: Forbid dividers. Use `spacing-8` (2.75rem) or `spacing-10` (3.5rem) to separate clauses or content blocks.

### Input Fields
- Underlined or ghost-styled. Background should be `surface_container_low` with a `rounded-md` (0.75rem) top-only radius. No heavy input boxes.

---

## 6. Do’s and Don'ts

### Do
- **DO** use significant white space. If you think there is enough space, add 20% more.
- **DO** use the `spacing-24` (8.5rem) for page margins to create an editorial, "centered" feel.
- **DO** use organic, diffused radial gradients in the background (`#F1F5F9` to `#FFFFFF`) to break the clinical coldness.
- **DO** use `backdrop-filter: blur()` on any panel that overlays the background gradients.

### Don't
- **DON'T** use 1px solid black or gray borders.
- **DON'T** use standard "drop shadows" with high opacity.
- **DON'T** use generic icons. Icons should be "Thin" or "Light" weight (1px to 1.5px stroke) to match the elegant Manrope typography.
- **DON'T** crowd the layout. If a legal document is long, use a clean, scrollable "Glass" panel rather than trying to fit it all on one screen.

---

## 7. Spacing & Grid

This system utilizes a **1440px Desktop Grid** but favors an "Artboard" approach over a rigid column grid. 

- **Outer Margin**: `spacing-20` (7rem).
- **Gutter**: `spacing-6` (2rem).
- **Section Gap**: `spacing-16` (5.5rem).

*Director's Note: Every element should feel like it was placed with surgical intent. If an element does not have a clear purpose or enough room to breathe, remove it.*