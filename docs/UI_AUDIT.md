# UI audit: what's real and what's only in the UI

> **Update, 28 Oct 2026:** the findings below were addressed by the UI upgrade (see the "Done" section of [UI_UPGRADE_COMPATIBILITY.md](UI_UPGRADE_COMPATIBILITY.md)).
>
> - Every fake number, person and success toast listed here was removed.
> - Unbuilt features are labelled "Coming soon".
> - Branding is unified, and the PostHog snippet is gone.
> - **Still not built** (shown as "Coming soon"): team members, billing, integrations, API keys, branding, notification preferences and two-factor authentication.
> - The score mislabelling and the backend parts of the Draft/department/salary issue depend on the backend fixes (BE-06, FE-02).
>
> The audit is kept as a record of the state before the upgrade.

Reviewed: every screen in `frontend/src/components` and the API calls behind it.

## Overall impression

The authenticated app looks modern and mostly consistent: an indigo "Precision Curator" palette, rounded cards, score rings, and a mobile bottom nav. What hurts credibility is not the styling but **fake numbers and dead buttons mixed with real data**. A recruiter with an empty workspace sees "1.2k candidates processed", "24 jobs" and "+12.5% vs last month". That reads as broken or dishonest, not professional.

Top fixes for a professional feel, in priority order:

1. **Remove hardcoded metrics and fallbacks.** Show real values or a proper empty state. The worst cases are the Dashboard (`|| '1.2k'`, `|| 24`, `|| 8`) and the QA page / Candidate Modal (invented title, email, phone and AI summary).
2. **Hide or clearly label unbuilt features** ("Coming soon" badge, disabled state) instead of buttons that do nothing or toasts that claim success.
3. **Pick one product name.** Login/Register say **"TrueView – AI Resume Screening"** (blue→purple gradient on dark slate), the app shell says **"ResumeAI – Precision Curator"** (indigo), and the browser tab says **"Resume AI"**. Bring Login/Register onto the same palette as the app.
4. **Fix the score labelling.** "Role Match %" actually shows the GitHub skills score (see Bugs).
5. **Remove the PostHog snippet** in `public/index.html`. It ships a hardcoded project key (probably left over from a template generator) and sends usage analytics to a third-party project you may not own. If you want analytics, use your own key and add consent.

---

## Screen by screen

Legend: ✅ works end-to-end · 🟡 partially real · ❌ UI only (hardcoded, or no handler)

### Login / Register
| Element | Status |
|---|---|
| Email/password sign-in and sign-up, Google sign-in (Firebase) | ✅ |
| Backend verification of the session | ✅ added on this branch (was missing) |
| "Forgot password" | ❌ missing entirely (Firebase `sendPasswordResetEmail` makes it easy) |

### Top navbar
| Element | Status |
|---|---|
| Page title / sub-title with chevron ("Recruitment Dept. ▾") | ❌ button with no handler |
| "Search insights…" | ❌ stores the text, searches nothing |
| Notification bell | ❌ unread dot always shown. Dropdown is hardcoded ("AI scans complete – 3 new candidates… 2 min ago"); "Mark all read" and "View all notifications" do nothing |
| Help icon | ❌ no handler |
| Avatar → Profile | ✅ |

### Sidebar
| Element | Status |
|---|---|
| Navigation, Logout | ✅ |
| "Help Center" | ❌ no handler |
| `aiQuota = 65` | unused dead variable |

### Dashboard (Overview)
| Element | Status |
|---|---|
| Recent Job Postings table | ✅ real jobs |
| "Global Reach" value | 🟡 real count, **falls back to "1.2k" when 0**. "+12.5% vs Last Month" is hardcoded; "last 30 days" isn't computed |
| Total Jobs / Active Jobs | 🟡 real, **falls back to 24 / 8 when 0** |
| "Avg Match Score 78% OPTIMAL" | ❌ hardcoded |
| Candidate avatar stack | ❌ grey placeholder circles |
| "View All" | ❌ no handler |
| "No Candidates Flagged for Review" card | ❌ always shown. "Import More" and "Run AI Scan" do nothing. "AI Pulse 89% Accuracy Index" is hardcoded |
| "Volume Analysis" bar chart | ❌ static array `[30, 60, 45…]`, labels "40W / FEB26", "Peak Performance 143 Candidates" |

### Job Postings
| Element | Status |
|---|---|
| List, create, edit, delete | ✅ |
| Candidate counts per job | ✅ now computed by the backend (was N+1 requests from the browser) |
| Action menu → "Archive" | ❌ only closes the menu |
| "Drafts" filter / Draft status | ❌ the backend only has `is_active`, so a job saved as **Draft is published as Active** and the Drafts tab is always empty |
| Job form: Department, Salary min/max | ❌ collected in the form but **dropped** by `transformJobToAPI`, so never saved |
| "Weekly Pipeline Health" card | ❌ hardcoded text ("grew by 14%", "128 leads", "Senior UX Designer"); "View Analytics" does nothing |

### Candidate Pipeline (per job)
| Element | Status |
|---|---|
| Upload resumes (drag/drop or picker) | ✅ |
| Upload / processing progress | ✅ **fixed on this branch**. It was a fake 1.5 s timer saying "processed by AI"; now it shows real queued, processing, done and failed counts |
| "Remaining" counter | ✅ **fixed**. It was `5 − candidates.length` |
| Candidate list, move to Interview | ✅ |
| "Pipeline Velocity 4.2 Days" | ❌ hardcoded |
| "N candidates meet the 80% threshold" | 🟡 threshold hardcoded, not linked to Settings → Scoring Thresholds |
| Upload zone says PDF/DOCX | 🟡 the backend also accepts `.txt`, but the file picker hides it |

### Candidate Modal (dossier)
| Element | Status |
|---|---|
| Name, status change | ✅ |
| Title "Professional", location "Remote" | ❌ defaults. The API doesn't return these fields |
| Bio / AI summary | ❌ always the generic placeholder ("…is a highly skilled Professional…"). The backend has a Gemini analysis endpoint (`ai_analysis_routes.py`, `GET /jobs/{id}/candidates/{id}/analysis`), but the router is **not mounted** in `main.py` and the UI never calls it |
| Top Skills, Education, Experience, GitHub/LinkedIn links | ❌ always empty. `getJobCandidates` doesn't return `skills`, `education`, `workExperience`, `githubProfile` or `linkedinUrl`, although the parsed resume contains them |
| "Experience Depth" ring | ❌ invented as the average of match and verification. Sub-label "Top 1% expertise" is hardcoded |
| Verification ring label "GitHub verified" | ❌ shown regardless of status |
| "Last sync: 14 min ago" | ❌ hardcoded |
| Status dropdown | 🟡 options (`New, Reviewing, …, Hired`) don't include the backend default **"Under Review"**, so the dropdown shows "New" for new candidates |

### Interviews
| Element | Status |
|---|---|
| Shortlisted/interview list, filters, search, status change | ✅ real (still N+1: one request per job) |

### Interview Q&A page
| Element | Status |
|---|---|
| AI-generated questions, keyword scoring, submit evaluation | ✅ |
| AI Fact Checker bot | ✅ |
| Candidate header | ❌ falls back to **"Senior Developer", "candidate@example.com", "+91 98200 45XXX", match 94%** and a canned quote ("Demonstrates high architectural maturity…"). Because the API doesn't send title or summary, real candidates show invented details |
| "Interview Type: Technical Round" | ❌ hardcoded |

### Account Settings (Profile)
| Element | Status |
|---|---|
| Personal info | ❌ pre-filled with **"Alex Rivera", "+1 (555) 892-0432", "San Francisco, CA"** when empty. "Save Changes" waits 600 ms and shows a success toast; nothing is saved. Editing the email doesn't change the login email |
| Notification preferences, AI parameters | ❌ local state only; "Save Preferences" is a fake success toast |
| "AI Efficiency Index 94.2%", Interview Rate 74%, Precision 96% | ❌ hardcoded |
| Change password | ❌ no handler |
| Multi-factor auth | ❌ "coming soon" toast |
| Active Sessions "MacBook Pro · London, UK · Active Now" | ❌ hardcoded |

### Workspace Settings — **the entire page is a mock-up**
| Tab | Status |
|---|---|
| Users | ❌ 4 fake people (`@neuralrecruit.ai`). "Invite User" is a 1 s timer plus "Invitation sent" toast; no email is sent. Row "⋯" menu does nothing. No roles exist in the backend |
| Billing | ❌ fake "Pro Plan 75/100", invoices "$99.00 Paid", "Visa •••• 4242". "Change Plan" and "Update card" do nothing |
| Integrations | ❌ toggles flip local state and toast "connected"; no Slack/Calendar/LinkedIn/Greenhouse/Teams integration exists |
| API Keys | ❌ fake masked keys. "Generate New Key" toasts success without creating a key; copy/rotate/revoke do nothing. The backend has no API-key auth |
| Customization | ❌ thresholds are not saved (1 s timer). "Save Branding" actually calls the thresholds handler. Logo upload shows "coming soon" |
| Insight panels / security card | ❌ hardcoded ("24% increase… Sarah Chen", "Last security check was 2 days ago") |

---

## Bugs found while auditing (not fixed on this branch)

- **Score mislabelled:** `GET /api/v1/jobs/{id}/candidates` returns `jd_match_score = score_details.skills_match_score`, which is the **GitHub verification score**. The real JD match (`score_details.jd_match_score`) is on a 0–10 scale. The UI shows the GitHub score as "Role Match %".
- **Candidate phone was always blank:** the route read `phone`, but the parser stores `phone_number`. **Fixed on this branch.**
- Deleting a job leaves its applications, tasks and uploaded files behind.

## Dead code to clean up

- `frontend/src/components/CandidateDetails.jsx` (not used anywhere), `CandidateDossier.jsx` (empty file), `frontend/src/mock.js` (not imported).
- Root `chat_design.html` (empty file), `backend/server.py` (old duplicate of the API with its own upload route), `backend/resume_parser.py`.
- `backend/requirements.txt` is UTF-16 encoded and pins Windows-only packages (`win32_setctime`, `pyreadline3`) plus `torch`. Convert it to UTF-8 and split dev and heavy dependencies to make deploys easier.
