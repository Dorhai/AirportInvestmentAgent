---
name: AirportIQ
description: ATFM Morning Briefing
colors:
  paper: "#fcfcfc"
  ink: "#111111"
  ink-muted: "#555555"
  hairline: "#e0e0e0"
  amber: "#d97706"
  red: "#dc2626"
  green: "#16a34a"
typography:
  sans:
    fontFamily: '"Inter", "Roboto", system-ui, sans-serif'
  mono:
    fontFamily: '"Menlo", "Consolas", ui-monospace, monospace'
rounded:
  none: "0px"
spacing:
  px: "1px"
  0.5: "0.125rem"
  1: "0.25rem"
  1.5: "0.375rem"
  2: "0.5rem"
  3: "0.75rem"
  4: "1rem"
  6: "1.5rem"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    typography: "{typography.sans}"
    rounded: "{rounded.none}"
    padding: "0.5rem 1.5rem"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.mono}"
    rounded: "{rounded.none}"
    padding: "0.375rem 1rem"
  input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.mono}"
    rounded: "{rounded.none}"
    padding: "0.5rem 1rem"
---

# Design System: AirportIQ

## Overview

**Creative North Star: "The Terminal Dashboard"**

AirportIQ is a data-dense, brutalist, and highly functional analytical interface. It evokes the feeling of air traffic control systems and terminal dashboards: high contrast, zero ornamentation, and absolute clarity. The aesthetic relies entirely on typography, strict borders, and a stark black-and-white foundation with semantic color used only for data status.

**Key Characteristics:**
- Monospace-heavy typography for data and labels.
- High-contrast, stark black and white foundation (`ink` and `paper`).
- Zero border radius; all corners are perfectly sharp.
- Dense layout with minimal padding.
- Semantic colors (amber, red, green) strictly reserved for status, confidence, and warnings.

## Colors

The palette is stark and utilitarian, relying on high contrast for readability.

### Primary
- **Ink** (#111111): The primary structural color. Used for text, primary borders, headers, and primary actions.
- **Paper** (#fcfcfc): The canvas. Used for application background and secondary element backgrounds.

### Secondary
- **Ink Muted** (#555555): Used for secondary text, metadata, and disabled states.
- **Hairline** (#e0e0e0): Used for subtle borders and dividers.

### Semantic
- **Green** (#16a34a): High confidence, positive opportunity scores, success.
- **Amber** (#d97706): Medium confidence, warnings, simulated/cached data indicators.
- **Red** (#dc2626): Low confidence, errors, active recording states.

**The Semantic Strictness Rule.** Semantic colors (green, amber, red) are never used for decoration. They appear only to convey data status, confidence levels, or system warnings.

## Typography

**Display/Sans Font:** Inter, Roboto (with system-ui fallback)
**Data/Mono Font:** Menlo, Consolas (with ui-monospace fallback)

**Character:** Utilitarian and data-focused. The sans-serif is used sparingly for primary UI actions and prose, while the monospace dominates the interface for labels, values, and metadata, often set in uppercase with wide tracking.

### Hierarchy
- **Primary Values** (bold, large): Used for key metrics and scores (e.g., 3xl for Opportunity Score, 2xl for KPIs).
- **Headers** (bold, sans): Used for application title and primary section headers.
- **Labels** (mono, uppercase, wide tracking, tiny): Used extensively for metadata, metric labels, and badges.

**The Mono-Data Rule.** Any numerical value, system status, or metadata label must be set in the monospace font.

## Layout

The layout is dense and functional. Elements are packed tightly to maximize data density on screen. Borders are used extensively to separate information rather than whitespace.

## Elevation & Depth

The system is entirely flat. Depth is conveyed through borders and high-contrast background changes (e.g., dark headers on light cards) rather than shadows.

**The Flat-By-Default Rule.** Surfaces are flat. Shadows are not used for structure or hierarchy.

## Shapes

The form language is strictly orthogonal. 

**The Razor Edge Rule.** There are no rounded corners anywhere in the system. Every button, input, card, and badge has a 0px border radius.

## Components

### Buttons
- **Shape:** Sharp corners (0px radius).
- **Primary:** Ink background, Paper text, bold sans-serif, uppercase.
- **Secondary / Action:** Paper background, Ink border, bold monospace, uppercase. Hover state inverts to Ink background and Paper text.

### Cards / Containers
- **Score Cards:** Heavy Ink border, with a dark Ink header for the title. Internal dividers use Hairline borders.
- **KPI Cards:** Hairline border, white background, dense internal layout.

### Inputs / Fields
- **Style:** Hairline border, Paper background, monospace text.
- **Focus:** Border changes to Ink. No glow or shadow.

### Badges
- **Style:** Tiny monospace text, uppercase, wide tracking, 1px border.
- **State:** Colors map strictly to confidence or status (Green/Amber/Red).

## Do's and Don'ts

### Do:
- **Do** use 1px borders to separate dense information.
- **Do** use uppercase monospace with wide tracking for labels and metadata.
- **Do** keep all corners perfectly sharp (0px radius).

### Don't:
- **Don't** use rounded corners on any element.
- **Don't** use shadows for elevation or hierarchy.
- **Don't** use semantic colors (green, amber, red) for structural or decorative elements.