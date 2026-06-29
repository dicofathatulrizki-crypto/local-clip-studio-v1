# ADR-001: React Frontend with TypeScript

**Status:** ✅ Approved  
**Date:** 2026-06-29  
**Author:** Principal Frontend Engineer

---

## Context

The application requires a desktop-grade user interface with complex interactive components: timeline editing, video preview, waveform rendering, transcript synchronization, and dockable panels. The UI must feel like a professional desktop application rather than a website. The existing project already uses React 19 + TypeScript + Vite + Tailwind + shadcn/ui.

## Decision

Adopt React 19 with TypeScript, Vite 7, Tailwind CSS 4, and shadcn/ui as the frontend technology stack. Use Zustand for state management. Use react-router for client-side routing. Use Framer Motion for animations.

## Rationale

- **React 19** — Latest stable React with concurrent features, server components (for future SSR), and improved hooks
- **TypeScript** — Type safety across the entire component tree; prevents runtime errors in complex state logic
- **Vite 7** — Fast HMR dev experience, optimized production builds, native ES module support
- **Tailwind CSS 4** — Utility-first CSS with design system tokens; consistent with existing project
- **shadcn/ui** — Collection of accessible, unstyled React components (Radix UI primitives); provides dialog, dropdown, tabs, slider, etc.
- **Zustand** — Lightweight state management; simpler than Redux for single-user desktop app; supports middleware for undo/redo
- **Framer Motion** — Declarative animation for timeline transitions, caption animations, and micro-interactions

## Alternatives Considered

| Alternative | Reason for Rejection |
|-------------|---------------------|
| Vue.js | Smaller ecosystem for desktop-grade editors; team has React expertise |
| Svelte | Smaller community; fewer component libraries |
| Redux | Too much boilerplate for single-user app; Zustand is simpler |
| Immer | Coupled to Redux; Zustand handles immutable updates natively |

## Consequences

- Timeline rendering requires Canvas or WebGL for performance (may need additional library)
- Large video processing means careful memory management in the browser
- React re-renders must be optimized for waveform and timeline (use memo, virtualization)
- State synchronization between React and Canvas requires careful architecture

## Trade-offs

- **Browser limitation:** Cannot access local filesystem directly (must use drag-and-drop or file picker + upload to backend)
- **GPU access:** Browser cannot directly access GPU for AI; all processing done on backend
- **Performance:** Heavy DOM updates may impact timeline scrubbing performance; require canvas-based rendering

---
