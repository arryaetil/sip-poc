# Etil

> Category: Professional Services & Public Sector
> Public-sector data, technology, policy and people consultancy within ibc group. Calm Night/Seasalt base, warm red→orange→yellow spectrum, Ubuntu throughout.

Source: *Etil – Brand Guideline EN 2026-07*. When in doubt, follow that guideline; this file summarises it for generation.

## 1. Visual Theme & Atmosphere

Etil makes complex public-sector topics clear, accessible and actionable. The look is **minimal in design, rich in meaning**: calm, analytical, human and trustworthy. Layouts are clean and structured with generous white space. Colour is used with purpose — to guide attention, clarify information and connect insight to impact — never as decoration.

The emotional signature is the **Etil spectrum**, a vertical or horizontal gradient from red to orange to yellow. It appears in key brand moments only: hero visuals, dividers, highlights and the logo claim system. Everything else rests on the neutral Night and Seasalt base.

Claim: **connecting insights to impact.** (always lowercase, with the full stop).

## 2. Color Palette & Roles

### Main palette (the base)
- **Night** (`#121212`): authority, focus and contrast. Titles, key messages, dark backgrounds, high-impact layouts, and almost all text.
- **Seasalt** (`#F8F9FA`): openness and clarity. Preferred background for reports, policy documents, dashboards, presentations and text-heavy applications.
- Tints of Night at 85%, 65%, 50% and 25% may be used for secondary text, borders and dividers.
- Neutral fallbacks: Dark Base `#111111`, White Base `#ffffff`.

### Etil spectrum (brand moments only)
`linear-gradient(180deg, #ff0020 0%, #ff4805 45%, #fea200 75%, #fbfb00 100%)` — the red→orange→yellow bar from the logo. Use it as a thin connector (a 3–6px bar, a divider, an accent edge), never as a full background.

### Service colour system (one per domain)
Use these consistently for service navigation, content clusters, icons, cards, highlights and diagrams:
- **Data** — Vermillion Red `#ff3333`: intelligence, evidence, urgency.
- **Technologie** — True Blue `#0066cc`: secure, scalable, future-ready public technology.
- **Beleid** — Soft Peach `#F1D490`: structure, governance, translation from insight into policy.
- **Menskracht** — Pumpkin Orange `#ff6600`: leadership, collaboration, implementation power.
- Bright Yellow `#ffff33` appears in the spectrum; use it only as a small highlight, never for text.

## 3. Typography

- **Ubuntu** is the only typeface (shared with ibc group). Fallback: **Arial**.
- **Titles**: Ubuntu **Bold**.
- **Subtitles and key messages**: Ubuntu **Light**, often in full lowercase.
- **Body copy and footnotes**: Ubuntu **Regular**.
- **Medium**: selectively, for highlights, subheadings and callouts.
- Keep hierarchy clear with weight and size, not with colour.

## 4. Logo Rules

- Use only the approved versions in `assets/`: black logo on light backgrounds, light logo on dark backgrounds. Do not use black and white versions together, and never recolour the logo.
- Keep the defined clear space around the logo; never crop it, place it in an unapproved container, rotate, stretch or distort it.
- Never place the logo on busy or low-contrast backgrounds.
- The spectrum is the bridge between logo and claim. Do not put it inside or behind the logo, integrate it into letters, stretch or rotate it, or overlap it with text.

Assets (in a studio project they are copied to `brand/`, e.g. `brand/etil-logo-slogan-white.svg`):
- **Dark backgrounds** (LinkedIn posts, title slides): `etil-logo-slogan-white.svg` — the complete light lockup: "Etil" wordmark, spectrum bar and claim. Show it whole, about 26% of the width, never cropped or masked.
- **Light backgrounds** (one-pagers, content slides): `etil-logo-slogan.png` — the same lockup in black.
- `etil-logo-black.svg` — black wordmark only; `etil-logo-claim-light.svg` — light wordmark with claim, stacked.
- **Never draw, recreate, simplify or generate a logo**, and never create logo files. If no official file fits, leave the logo out.

## 5. Tone of Voice

Clear, knowledgeable and public-minded; calm, confident and accessible.
- **Clear** — make complexity understandable.
- **Evidence-based** — ground messages in data, research and expertise.
- **Human** — write for people, not systems.
- **Confident** — know the field without sounding distant or academic.
- **Action-oriented** — connect insight to decisions, implementation and public impact.

Avoid unnecessary jargon, inflated claims and overly commercial language. Never invent customers, results, figures or capabilities: only state what the supplied Business Context or source material supports. Dutch is the default language for Dutch audiences.

## 6. Imagery

Visuals express insight, connection, governance, public environments, regional development, collaboration and data-driven decision-making. Prefer compositions that feel intelligent and human, not overly corporate, abstract or technology-driven without context. Every image supports one clear idea: insight that leads to public impact. Four colour worlds — Data, Technologie, Beleid, Menskracht — each lean on their service colour, connected by the spectrum.

AI-generated images must carry the label **"AI-GENERATED VISUAL — provided by ibc group marketing"** (small outlined pill, bottom right), as in the official templates.

## Image library and AI labels

Prefer these approved images over generating new ones: `assets/images/case-1.jpg`, `assets/images/case-2.jpg`, `assets/images/case-3.jpg`, `assets/images/case-4.jpg`, `assets/images/case-5.jpg`, `assets/images/case-6.jpg`, `assets/images/etil-etil-header-2.jpg`, `assets/images/etil-header-v1-1.jpg`, `assets/images/etil-ibc-beleid-2.jpg`, `assets/images/etil-ibc-group-process-teaser-2.jpg`, `assets/images/etil-ibc-menskracht-3.jpg`, `assets/images/etil-services-hero.jpg`. They already carry the AI notice where needed.

From the *AI-Generated Images Guideline*: always label an image when someone could think it is real (photo-like, used in marketing, social media or external communication, or shareable on its own). Place the label directly on the image, small and discreet, bottom right: **"AI-generated image – created by IBC Group Marketing"** (short: "AI-generated | IBC Group Marketing"). When in doubt, label. Do not use Creative Commons images without the author attribution from the licence library; ask marketing instead.

## 7. LinkedIn post pattern (from the official templates)

Portrait 4:5 (1080×1350). Examples in `assets/examples/linkedin-*.jpg` — match them closely.
- Full-bleed dark image in the colour world of the domain (Data red/pink, Technologie blue, Beleid silver/soft peach, Menskracht orange), darker on the left so text reads.
- Top left: a short thin white rule, then "Perspective on" in Ubuntu Light, then the domain name in capitals in its service colour (BELEID `#F1D490`, DATA `#ff3333`, MENSKRACHT `#ff6600`, TECHNOLOGIE `#0066cc`).
- Below: one short statement in white Ubuntu Bold, large (about 7% of the width), three to four lines, ending with a full stop. One idea, no hashtags on the image.
- Bottom left: the light Etil logo with the claim "connecting insights to impact." and "part of ibc group".
- Bottom right: the AI-generated visual label when the image is AI-generated.

## 8. Fonts

Ubuntu Light, Regular, Medium and Bold ship in `fonts/` (Ubuntu Font Licence, `fonts/UFL.txt`). Load them with `@font-face`; never substitute another family unless Ubuntu cannot load, then Arial.

## 9. Layout & Components

- Seasalt or white backgrounds for content; Night for title slides, key messages and hero sections.
- Cards: flat, 1px Night-15% border or no border on Seasalt, small radius (4–8px), no heavy shadows.
- A thin spectrum bar may mark the top of a hero, a section divider or a highlighted card.
- Service colour appears as a small marker (dot, tag, left border, icon) that labels the domain, not as a large fill.
- Buttons and links: Night fill with white text, or True Blue for links in digital contexts.
- Footer line on documents: "connecting insights to impact. | © Etil".
