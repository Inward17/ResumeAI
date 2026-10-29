# ResumeAI — frontend

React 19 + Vite + Tailwind CSS 3, with Firebase Authentication (Google / email sign-in).

## Setup

```bash
cp .env.example .env   # fill in VITE_API_URL and the VITE_FIREBASE_* values
yarn install
```

## Scripts

| Command | What it does |
|---|---|
| `yarn dev` (or `yarn start`) | Dev server on http://localhost:3000 with hot reload |
| `yarn build` | Production build into `dist/` |
| `yarn preview` | Serve the production build on http://localhost:3000 |

`dist/` is a static single-page app. Configure your host to serve `index.html` for unknown paths so deep links like `/jobs/<id>` work on refresh (e.g. Netlify `_redirects`: `/* /index.html 200`; Vercel/Firebase Hosting: a rewrite to `/index.html`).

## Structure

- `src/App.jsx` — routes (`/dashboard`, `/jobs`, `/jobs/:jobId`, `/jobs/:jobId/candidates/:candidateId/interview`, `/interviews`, `/settings`, `/profile`, `/login`, `/register`)
- `src/components/` — pages; `common.jsx` (cards, pills, score rings, buttons) and `Modal.jsx` (accessible dialog) are shared
- `src/services/` — API calls (`api.js` adds the sign-in token to every request)
- `src/lib/statuses.js` — candidate and job statuses (must match the backend)
- `tailwind.config.js` — brand colours (`brand`, `brand-accent`, `brand-cyan`, `page`, `bg-brand-gradient`)
