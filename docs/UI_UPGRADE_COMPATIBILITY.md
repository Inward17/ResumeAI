# UI: can it be upgraded, and is it compatible?

**Short answer: yes, it can be upgraded, and nothing blocks it.** The app is small (about 15 screens, ~5k lines of JSX), already on React 19 and React Router 7, and mostly uses plain Tailwind classes.

The main liability is the **build tool**. Create React App (`react-scripts` 5, wrapped by CRACO) is deprecated and unmaintained, and it is the source of most of the 80 `npm audit` findings.

How this was checked:
- `npm outdated` and `npm audit`
- Usage analysis of every dependency
- A production build
- A scripted run through every main screen in headless **Chromium** at 1440×900, 820×1180 and 390×844, with auth stubbed and the API mocked

Screenshots are in [`ui-review/`](ui-review/).

---

## ✅ Done on 28 Oct 2026

Steps 1–4 of the upgrade path (§4) are complete. Tailwind 4 and lucide-react 1.x were deliberately left out.

**What changed**

- **Build tool:** Create React App/CRACO → **Vite 6** (`yarn dev` / `yarn build` / `yarn preview`, port 3000, output `dist/`). Pages are lazy-loaded, and React/Firebase sit in separate vendor chunks (largest chunk ~84 kB gzipped; no size warnings). Build time is ~3 s.
- **Environment variables:** `REACT_APP_*` → **`VITE_*`**:
  - `VITE_API_URL`
  - `VITE_FIREBASE_API_KEY`, `_AUTH_DOMAIN`, `_PROJECT_ID`, `_STORAGE_BUCKET`, `_MESSAGING_SENDER_ID`, `_APP_ID`, `_MEASUREMENT_ID`

  Rename them in your `frontend/.env`.
- **Dependencies:**
  - Removed 14 unused packages (`axios`, `zod`, `react-hook-form`, `@hookform/resolvers`, `date-fns`, `embla-carousel-react`, `cmdk`, `vaul`, `input-otp`, `react-day-picker`, `react-resizable-panels`, `next-themes`, `sonner`, `cra-template`), plus `react-scripts`, CRACO, the unconfigured ESLint packages and 23 unused Radix packages.
  - Removed 41 unused `components/ui/*` files.
  - Updated: `react-router-dom` 7.18, `firebase` 12.19.
  - One lockfile (`yarn.lock`).
  - Audit findings **80 → 4**. The 4 left (2 high, 2 low) are all `@grpc/grpc-js`, a Node-only dependency of Firestore inside the `firebase` package. The app only imports `firebase/auth`, so this code is never bundled or shipped. It clears when Firebase updates that dependency.
- **Real URLs:** `/dashboard`, `/jobs`, `/jobs/:jobId` (dossier via `?candidate=<id>`), `/jobs/:jobId/candidates/:candidateId/interview`, `/interviews`, `/settings`, `/profile`, `/login`, `/register`.
  - Refresh, the Back button and shared links work.
  - Signed-out users are sent to `/login` and returned to the page they wanted.
- **Design system:**
  - Brand colours are Tailwind tokens (`brand`, `brand-accent`, `brand-light`, `brand-soft`, `brand-cyan`, `page`, `bg-brand-gradient`).
  - `theme.js` / `theme.css` and almost all inline colour styles are gone.
  - Shared `common.jsx` (cards, pills, score rings, buttons, empty states) and an accessible `Modal.jsx` (Radix Dialog).
- **Honesty pass:**
  - Every invented number, person and canned text was removed (Dashboard, pipeline, dossier, interview page, Profile, Settings, notifications).
  - Unbuilt features (team, billing, integrations, API keys, branding, notifications, 2FA) are labelled **Coming soon**.
  - Buttons either work or are gone.
  - New, real features: scoring thresholds (saved per browser, used by pipelines/dossiers), password reset email, display-name change, Close/Reopen job, candidate search and status filter.
- **Accessibility:**
  - Readable text uses `slate-500`+ (no more 2.5:1 grey).
  - Icon-only buttons have labels.
  - Dialogs close on Escape and trap focus.
  - Visible keyboard focus ring.
- **Brand:** "ResumeAI" everywhere, with Login/Register on the app's indigo theme. PostHog snippet removed.

**Bugs fixed:** FE-01 (config-missing screen instead of a blank page), FE-02 (frontend part: status/department/salary sent; Drafts filter), FE-03, FE-04, FE-05 (one status list), FE-06 (real dossier fields), FE-07, FE-08, FE-09, FE-10, FE-11.

**Verified:**
- Re-ran the Chromium review at 1440/820/390 px with the new API contract mocked: no page errors and no horizontal overflow.
- Escape closes both dialogs; refresh on `/jobs/:id` keeps the page; deep links open the dossier.
- Drafts filter works; status changes send canonical values; `/login` redirects signed-in users; protected pages redirect signed-out users.

Safari and Firefox are still untested; only Chromium is available here.

> The sections below describe the state **before** this upgrade and are kept for reference.

---

## 1. Device / browser compatibility (tested)

| Check | Result |
|---|---|
| Desktop 1440 px | ✅ renders well, no overflow |
| Tablet 820 px | ✅ works. The sidebar stays expanded (224 px), so content is cramped, and the Settings team table pushes the **Actions** column off-screen (horizontal scroll inside the card) |
| Phone 390 px | ✅ genuinely responsive: bottom tab bar, stacked cards, bottom-sheet candidate modal, Pipeline/Analysis tab switch. No page-level horizontal scroll on any tested screen |
| Runtime errors | none in Chromium across the full flow |
| Safari / Firefox | **not tested.** Only Chromium is available in this environment. The current Tailwind 3 + CRA/Babel setup targets `>0.2%, not dead`, so no known blockers |
| Missing Firebase config | ❌ **completely blank white page** (`auth/invalid-api-key` thrown at import). A fresh clone or misconfigured deploy shows nothing. Fix: validate env at startup and render an error screen |

## 2. Accessibility (affects "professional" and compliance)

| Issue | Detail |
|---|---|
| Low-contrast text | `text-slate-400` (#94a3b8) is used **110×** for labels and sub-text: **2.56:1** on white and 2.31:1 on the page background (WCAG AA needs 4.5:1). `text-slate-300` (9×) is 1.48:1. Use `slate-500` (4.76:1) or darker |
| Icon-only buttons | Bell, help, close (×) and row chevrons have no `aria-label`. There are **0** `aria-label`s in app components |
| Candidate modal | Custom `div` overlay: **Escape doesn't close it**, no focus trap, no `role="dialog"`/`aria-modal`. The Radix `Dialog` already in `components/ui/dialog.jsx` provides all of this |
| Navigation | Views switch through React state under a single `/dashboard` URL. **Refresh and the browser back button lose your place**, you can't link to a job or candidate, and screen readers get no page change |

## 3. Dependency health

### Unused dependencies (safe to remove)

App code never imports `axios`, `zod`, `react-hook-form`, `@hookform/resolvers`, `date-fns`, `embla-carousel-react`, `cmdk`, `vaul`, `input-otp`, `react-day-picker`, `react-resizable-panels`, `next-themes`, `sonner` or `cra-template`. Some of them are only referenced by unused shadcn files.

**Only ~15 of the 46 files in `components/ui/` are used.** Removing the rest and these packages cuts install size and several audit findings (`axios`, `zod`).

### Security audit (80 findings: 4 critical, 38 high)

- **Build-time only (not shipped to users):** `webpack-dev-server`, `express`, `svgo`, `nth-check`, `workbox-build`, `serialize-javascript` and others. These all come from `react-scripts` and go away with the move to Vite.
- **Runtime:**
  - `react-router(-dom)` 7.9.4: high. Fixed by `npm update` within 7.x (7.18.5).
  - `axios` and `zod`: unused, remove.
  - `protobufjs` / `@grpc/grpc-js`: pulled in by `firebase`. Update to firebase 12.19+ or 13.

### Version status

| Package | Current | Latest | Upgrade notes |
|---|---|---|---|
| react / react-dom | 19.2.0 | 19.3.1 | drop-in |
| react-router-dom | 7.9.4 | 7.18.5 | drop-in (security fix) |
| firebase | 12.8.0 | 13.1.0 | 12.19 drop-in; 13 is a major, but the app only uses `firebase/auth` basics (low risk) |
| radix-ui/* | 1.1–2.2 | 1.2–2.4 | drop-in minors |
| tailwindcss | 3.4.18 | 4.3.3 | **major**, see §4 |
| lucide-react | 0.507 | 1.63 | **major: brand icons removed.** `Github` (used in CandidatePipeline and CandidateModal) no longer exists. Swap in an SVG or `simple-icons` |
| eslint | 9.23 | 10.13 | dev only; CRA's lint config doesn't support it |
| zod / hookform / react-day-picker / react-resizable-panels | — | majors | unused, remove instead of upgrading |
| react-scripts | 5.0.1 | deprecated | **replace with Vite**, see §4 |

There are also two lockfiles (`yarn.lock` and `package-lock.json`) while `package.json` pins `packageManager: yarn`. Keep one.

## 4. Recommended upgrade path

Each step can ship on its own.

1. **Housekeeping (low risk, ~½ day)**
   - Remove unused packages and `components/ui` files.
   - `npm update` (React Router security fix, Firebase 12.19, Radix minors).
   - Pick one lockfile.
   - Remove the third-party PostHog snippet from `public/index.html`.
2. **CRA → Vite (~1 day).** It's compatible; the changes needed:
   - JSX lives in `.js` files (`App.js`, `index.js`, `context/AuthContext.js`): rename them to `.jsx` (or configure esbuild's loader).
   - `process.env.REACT_APP_*` (in `firebase.js` and `services/api.js`) → `import.meta.env.VITE_*`, and rename the vars in `.env`.
   - `@` alias from `craco.config.js` → `resolve.alias` in `vite.config.js`.
   - `public/index.html` → root `index.html` with `<script type="module" src="/src/index.jsx">`.
   - Tailwind 3 + PostCSS config works unchanged under Vite.
   - Result: dev server starts in about a second instead of 10–20 s, and the 70+ build-tool vulnerabilities disappear.
3. **Real URLs (~1 day).** React Router 7 is already installed but only used for `/login` and `/dashboard`. Add routes such as `/jobs`, `/jobs/:jobId`, `/jobs/:jobId/candidates/:candidateId`, `/interviews` and `/settings`. This fixes refresh, back button and shareable links.
4. **Design-system cleanup (gradual).** Styling currently mixes four sources:
   - Tailwind classes
   - **185 inline `style={{…}}` objects**
   - **148 hard-coded hex colours**
   - `theme.js` constants plus `theme.css` variables

   Move the colours into Tailwind theme tokens (`primary`, `accent`, …) so the palette lives in one place. That also enables dark mode and makes Tailwind 4 migration mechanical. Fix contrast (§2) in the same pass.
5. **Tailwind 3 → 4 (optional, after 4).**
   - CSS-first config replaces `tailwind.config.js`.
   - `tailwindcss-animate` → `tw-animate-css`.
   - Some utilities were renamed (`shadow-sm`→`shadow-xs`, `rounded-sm`→`rounded-xs`, `outline-none`→`outline-hidden`; default ring width changes).
   - shadcn components need their v4 versions.
   - **Browser floor rises to Safari 16.4 / Chrome 111 / Firefox 128.** Check that's acceptable for your users first. If any are on older corporate browsers, stay on Tailwind 3 (still maintained).
6. **lucide-react 1.x:** replace the `Github` brand icon first.

## 5. Front-end ↔ back-end contract (compatible, with these mismatches)

All frontend calls match existing backend routes and payloads (jobs CRUD, upload, candidates, tasks, status, interview questions, evaluation, fact checker, `/api/auth/me`). Mismatches:

- **Scores:** `jdMatchScore` shown as "Role Match %" is the backend's GitHub score; the real JD match is `score_details.jd_match_score` on a 0–10 scale. See BACKEND_ANALYSIS P1 #9.
- **Status vocabulary:** backend default `"Under Review"`; Candidate Modal options are `New/Reviewing/Shortlisted/Interview/Offer/Hired/Rejected`; Interviews filters lowercase variants too. The backend accepts any string, so define one enum on both sides.
- **Missing fields:** the candidate list API doesn't return skills, education, experience, GitHub/LinkedIn links or an AI summary, so those modal sections are always empty or placeholder (see UI_AUDIT.md). Either extend `GET /jobs/{id}/candidates` or add `GET /candidates/{id}`.
- **Job form:** `department`, `salaryMin/Max` and the `Draft` status aren't in the API model, so they're silently dropped (Draft becomes Active).
- **Interviews page** still fetches every job's candidate list (N+1). Add `GET /api/v1/interviews` or a status filter on the candidates endpoint.
