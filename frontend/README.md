# ResumeAI — frontend

React 19 + Vite 6 + Tailwind CSS 3, with Firebase Authentication (Google or email sign-in).

## Setup

```bash
cp .env.example .env   # VITE_API_URL and the VITE_FIREBASE_* values from Firebase console → Project settings
yarn install
```

If a Firebase value is missing, the app shows a "Configuration missing" screen listing what to set.

## Scripts

| Command | What it does |
|---|---|
| `yarn dev` (or `yarn start`) | Dev server on http://localhost:3000 with hot reload |
| `yarn build` | Production build into `dist/` |
| `yarn preview` | Serve the production build on http://localhost:3000 |

The backend only accepts browser requests from origins in its `CORS_ORIGINS`, so add any other port you run on.

`dist/` is a static single-page app. Configure your host to serve `index.html` for unknown paths so deep links like `/jobs/<id>` work on refresh (Netlify `_redirects`: `/* /index.html 200`; Vercel or Firebase Hosting: a rewrite to `/index.html`).

## Routes

| Path | Page |
|---|---|
| `/dashboard` | Overview: headline numbers, recent jobs |
| `/jobs`, `/jobs/:jobId` | Jobs, and a job's ranked candidate pipeline (`?candidate=<id>` opens a dossier) |
| `/jobs/:jobId/candidates/:candidateId/interview` | Interview kit and fact checker |
| `/interviews` | Shortlisted and interview-stage candidates across jobs |
| `/settings` | `?tab=` `team`, `api-keys`, `usage`; default is appearance and scoring |
| `/profile` | Account and sign-in settings |
| `/join/:token` | Accept a workspace invitation |
| `/login`, `/register` | Sign in / sign up (they return you to the page you were going to) |

## Structure

- `src/App.jsx` — routes; pages are lazy-loaded.
- `src/components/common.jsx` — the shared UI kit: buttons, fields, cards, status dots, score bars and rings, stat strip, menu, segmented filter. Build new screens from these.
- `src/components/Modal.jsx` — accessible dialog and `ConfirmDialog` (use it instead of `window.confirm`).
- `src/components/WorkspaceSettings.jsx` — Team, API keys, Plan & usage settings sections.
- `src/services/` — API clients. `api.js` adds the sign-in token to every request; `jobService.js` maps snake_case API fields to camelCase.
- `src/lib/theme.js` — light / dark / system theme (`index.html` applies it before first paint).
- `src/lib/statuses.js` — candidate and job statuses; must match the backend.

## Design tokens

Colours are CSS variables in `src/index.css` (light under `:root`, dark under `.dark`) exposed as Tailwind colours in `tailwind.config.js`. Use the semantic names, never raw palette colours, so both themes keep working:

| Token | Use |
|---|---|
| `canvas`, `surface`, `subtle` | Page background, cards and inputs, hover fills and wells |
| `line`, `line-strong` | Hairline borders, input borders |
| `ink`, `ink-2`, `ink-3` | Primary, secondary and muted text |
| `btn`, `btn-fg` | Solid (primary) buttons — ink in light mode, cream in dark |
| `primary` (`-text`, `-soft`, `-soft-fg`) | Forest-green accent: links, focus, progress, active states |
| `success`, `warning`, `danger`, `info` (+ `-soft`) | Status colours |

Type: Geist for the interface, Instrument Serif (`font-serif`) for page titles and headline numbers only.
