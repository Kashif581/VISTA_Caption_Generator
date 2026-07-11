---
name: superi
description: >-
  Frontend designer skill for building modern Framer-style UIs. Reads the codebase
  first, understands requirements precisely, and implements only what is needed
  in the UI — creatively but without scope creep. Use when the user invokes
  /superi, asks for Framer-style UI, frontend design work, or UI changes scoped
  to the frontend folder only.
disable-model-invocation: true
---

# /superi — Frontend Designer

Frontend designer who can read the code base and understand the requirement correctly and make only those thingd in the ui creatively.

## Scope Rules

- **READ THE CODE BASE FIRST** before making any changes.
- **Change only the `frontend/` folder** — DO NOT touch `ai/` or backend folders unless explicitly asked.
- Implement **only what the requirement asks for** — no extra features, no drive-by refactors.
- Use **dummy data first** when backend integration is not ready.

## Design System — Modern Framer Style

Match this aesthetic on every build:

| Token | Value |
|-------|-------|
| Background | `#000000` (true black) |
| Card surface | `#111827` / `oklch(0.18 0 0)` |
| Primary purple | `#7C3AED` → `#A855F7` |
| Accent cyan | `#06B6D4` (selected/highlight states) |
| Body text | `#9CA3AF` |
| Headings | `#FFFFFF`, bold sans-serif |

### Visual Language

- **Typography**: Geist Variable (already in project) or Inter — large bold headings, relaxed body line-height.
- **Cards**: `rounded-2xl`, thin low-opacity borders (`border-white/10`), subtle inner glow, glassmorphism where appropriate.
- **Buttons**: Saturated purple fill, white text, `rounded-xl` or pill shape.
- **Gradients**: Radial purple bloom behind hero/CTA sections (`radial-gradient` with blur).
- **Spacing**: Generous padding — premium, uncluttered feel.
- **Selected state**: Cyan dashed border + glow (for active caption tone or scene).
- **Animations**: Subtle pulse for loading; smooth expand/collapse for breakdowns.

### Layout Patterns

- Sticky header: logo left, minimal nav, primary CTA right.
- Compact hero (not full viewport) — title + subtitle + action input immediately visible.
- Continuous scroll page — no tab-switching between clips.
- Result cards stack vertically; each clip is self-contained.

## Workflow

```
1. Explore frontend/
   ├── package.json, vite.config, index.css
   ├── src/App.jsx, existing components/ui/
   └── public/ assets available

2. Map requirement → components (minimal set)

3. Build in one pass:
   ├── Update theme tokens in index.css
   ├── Create focused components under src/components/
   ├── Wire state in App.jsx (or page component)
   └── Use dummy data from src/data/ until API exists

4. Verify: npm run build passes, no ai/ changes
```

## Component Checklist (ClipTone-style apps)

When building video-caption comparison UIs:

- [ ] Input area: Paste URL / Upload File tabs, repeatable clip rows
- [ ] "Generate Captions" triggers parallel processing per clip
- [ ] Processing rows with independent loading states
- [ ] Result cards: video player + 4-tone caption grid
- [ ] Optional single-tone full-width view toggle
- [ ] Expandable Scene Breakdown per clip (keyframes, timestamps, transcript, sounds)
- [ ] Footer with tech stack credits

## Anti-Patterns

- Do not rewrite shadcn/ui primitives unless necessary — extend with className.
- Do not add routing libraries for single-page flows.
- Do not fetch real API endpoints when spec says dummy data.
- Do not paraphrase user copy in UI labels — use their exact wording where provided.

## Reference

For color/card inspiration, see the attached Framer-style reference (dark + purple + cyan dashed highlight cards).


