"""Portfolio and community claims on a resume, cross-checks, and job-skill evidence.

None of this changes credibility or role match: it adds discrepancies and
evidence for the reviewer only.
"""
import re
from typing import List, Optional, Tuple

from rapidfuzz import fuzz

from app.services.coding_profiles.claims import _LINK_RE, _SENTENCE_RE, name_conflicts
from app.services.portfolios.fetchers import KAGGLE_TIERS

LABEL = {"behance": "Behance", "dribbble": "Dribbble", "website": "Portfolio website", "kaggle": "Kaggle",
         "stackoverflow": "Stack Overflow"}

_KAGGLE = re.compile(r"\bkaggle\b", re.I)
_SO = re.compile(r"\bstack\s?overflow\b", re.I)
_KAGGLE_TIER = re.compile(r"\b(?:(competitions?|datasets?|notebooks?|code|discussions?)\s+)?"
                          r"(grandmaster|master|expert|contributor)\b", re.I)
_NUM = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k)?"
_REPUTATION = re.compile(rf"{_NUM}\s*\+?\s*(?:reputation|rep)\b|reputation\D{{0,15}}?{_NUM}", re.I)
_TOP_PERCENT = re.compile(r"\btop\s+(\d+(?:\.\d+)?)\s*%", re.I)

REPUTATION_RATIO = 0.8
# Stack Exchange publishes no percentile in its API, so a "top N%" claim is only
# flagged when reputation is far below any plausible threshold.
# ponytail: fixed floors; swap for the site's real percentile if the API ever exposes it
_TOP_PERCENT_FLOORS = [(1, 1000), (5, 200), (10, 100)]


def _category(word: Optional[str]) -> Optional[str]:
    if not word:
        return None
    word = word.lower()
    return "notebooks" if word == "code" else word if word.endswith("s") else word + "s"


def _number(digits: str, k: Optional[str]) -> int:
    return int(float(digits.replace(",", "")) * (1000 if k else 1))


def detect_claims(text: str) -> List[dict]:
    """Claims like "Kaggle Competitions Master", "10k reputation on Stack Overflow", "top 1% on Stack Overflow"."""
    claims = []
    for sentence in _SENTENCE_RE.split(_LINK_RE.sub(" ", text or "")):
        snippet = sentence.strip()[:120]
        if _KAGGLE.search(sentence):
            for m in _KAGGLE_TIER.finditer(sentence):
                claims.append({"platform": "kaggle", "kind": "tier", "value": m.group(2).lower(),
                               "category": _category(m.group(1)), "text": snippet})
        if _SO.search(sentence):
            m = _REPUTATION.search(sentence)
            if m:
                digits, k = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
                claims.append({"platform": "stackoverflow", "kind": "reputation", "value": _number(digits, k),
                               "text": snippet})
            m = _TOP_PERCENT.search(sentence)
            if m:
                claims.append({"platform": "stackoverflow", "kind": "top_percent", "value": float(m.group(1)),
                               "text": snippet})
    unique = {(c["platform"], c["kind"], c["value"], c.get("category")): c for c in claims}
    return list(unique.values())


def _check_claim(claim: dict, p: dict) -> Optional[str]:
    kind, value = claim["kind"], claim["value"]
    if kind == "tier":
        tiers = p.get("tiers") or {}
        if not tiers:
            return None
        cat = claim.get("category")
        if cat and cat not in tiers:
            return None  # that category wasn't read from the page
        actual = tiers[cat] if cat else max(tiers.values(), key=KAGGLE_TIERS.index)
        if KAGGLE_TIERS.index(value) > KAGGLE_TIERS.index(actual):
            where = f"{cat} " if cat else ""
            return f"Resume claims Kaggle {where}{value.title()}; profile shows {actual.title()}"
    rep = p.get("reputation")
    if rep is None:
        return None
    if kind == "reputation" and rep < value * REPUTATION_RATIO:
        return f"Resume claims {value:,} Stack Overflow reputation; profile shows {rep:,}"
    if kind == "top_percent":
        floor = next((f for pct, f in _TOP_PERCENT_FLOORS if value <= pct), None)
        if floor and rep < floor:
            return f"Resume claims top {value:g}% on Stack Overflow; reputation is only {rep:,}"
    return None


# ── Resume contradictions (experience, education) ──────────────────

_YEAR = re.compile(r"\b(19[5-9]\d|20\d\d)\b")
_PRESENT = re.compile(r"\b(present|current|now|ongoing)\b", re.I)


def _years(text: Optional[str]) -> Optional[Tuple[int, int]]:
    years = [int(y) for y in _YEAR.findall(text or "")]
    if not years:
        return None
    end = 9999 if _PRESENT.search(text) else max(years)
    return min(years), end


_DEGREES = [
    (r"\bph\.?\s?d\b|\bdoctor(ate)? of", "phd"),
    (r"\bm\.?\s?b\.?\s?a\b|master of business", "mba"),
    (r"\bm\.?\s?c\.?\s?a\b|master of computer applications", "mca"),
    (r"\bm\.?\s?tech\b|\bm\.?\s?e\b\.?|master of (technology|engineering)", "mtech"),
    (r"\bm\.?\s?des\b|master of design", "mdes"),
    (r"\bm\.?\s?f\.?\s?a\b|master of fine arts", "mfa"),
    (r"\bm\.?\s?sc?\b|master of science", "msc"),
    (r"\bm\.?\s?a\b|master of arts", "ma"),
    (r"\bb\.?\s?tech\b|\bb\.?\s?e\b\.?|bachelor of (technology|engineering)", "btech"),
    (r"\bb\.?\s?des\b|bachelor of design", "bdes"),
    (r"\bb\.?\s?f\.?\s?a\b|bachelor of fine arts", "bfa"),
    (r"\bb\.?\s?c\.?\s?a\b|bachelor of computer applications", "bca"),
    (r"\bb\.?\s?b\.?\s?a\b|bachelor of business", "bba"),
    (r"\bb\.?\s?sc?\b|bachelor of science", "bsc"),
    (r"\bb\.?\s?a\b|bachelor of arts", "ba"),
    (r"\bdiploma\b", "diploma"),
]
_DEGREES = [(re.compile(rx, re.I), key) for rx, key in _DEGREES]


def _degree(text: Optional[str]) -> Optional[str]:
    return next((key for rx, key in _DEGREES if rx.search(text or "")), None)


def _strings(values) -> List[str]:
    return [v for v in values or [] if isinstance(v, str) and v.strip()]


def _resume_conflicts(p: dict, resume: dict) -> List[str]:
    """Experience with a different employer for the same dates, or a different degree at the same institution."""
    issues = []
    experience, education = _strings(resume.get("experience")), _strings(resume.get("education"))
    for job in p.get("experience") or []:
        org, dates = job.get("organisation"), _years(job.get("dates"))
        if not org or not dates or any(fuzz.partial_ratio(org.lower(), line.lower()) >= 80 for line in experience):
            continue
        same = [line for line in experience if _years(line) == dates]
        if same:
            issues.append(f"{LABEL[p['platform']]} lists {job.get('role') or 'a role'} at {org} ({job['dates']}); "
                          f"the resume has \"{same[0][:100]}\" for the same dates")
    for ed in p.get("education") or []:
        inst, degree = ed.get("institution"), _degree(ed.get("degree"))
        if not inst or not degree:
            continue
        lines = [line for line in education if fuzz.partial_ratio(inst.lower(), line.lower()) >= 85]
        resume_degrees = {_degree(line) for line in lines} - {None}
        if resume_degrees and degree not in resume_degrees:
            issues.append(f"{LABEL[p['platform']]} lists {ed['degree']} at {inst}; the resume has "
                          f"\"{lines[0][:100]}\"")
    return issues


def _real_name(name: Optional[str]) -> bool:
    """Display names like "ada_dev" are handles, not names; compare only two or more words of letters."""
    return bool(name) and len(re.findall(r"[^\W\d_]{2,}", name)) >= 2 and not re.search(r"[\d_@]", name)


def check_portfolios(entries: List[dict], claims: List[dict], resume: Optional[dict]) -> Tuple[str, List[dict]]:
    """Add issues to each found entry; return (status, discrepancies as dicts).

    status: verified, unverified (a name conflict, contradiction or overstated claim),
    not_found, not_configured (Firecrawl missing or switched off), or pending.
    """
    resume = resume or {}
    resume_name = (resume.get("personal_info") or {}).get("full_name")
    found = {p["platform"]: p for p in entries if p.get("status") == "found"}
    discrepancies = []

    def flag(p, field, msg, resume_value, severity="major"):
        p.setdefault("issues", []).append(msg)
        discrepancies.append({"field": field, "source": p["platform"], "resumeValue": resume_value,
                              "actualValue": msg, "severity": severity, "description": msg})

    for p in found.values():
        if _real_name(p.get("name")) and name_conflicts(p["name"], resume_name):
            flag(p, "name", f"Name on {LABEL[p['platform']]} ({p['name']}) differs from the resume", resume_name)
        for msg in _resume_conflicts(p, resume):
            flag(p, "portfolio_history", msg, None)
    for claim in claims or []:
        p = found.get(claim.get("platform"))
        msg = _check_claim(claim, p) if p else None
        if msg:
            flag(p, f"portfolio_{claim['kind']}", msg, claim.get("text"))

    for p in entries:
        if p.get("status") == "not_found":
            msg = f"{LABEL.get(p['platform'], p['platform'])} profile '{p.get('handle')}' listed on the resume doesn't exist (check for a typo)"
            discrepancies.append({"field": "portfolio_profile", "source": p["platform"], "resumeValue": p.get("handle"),
                                  "actualValue": "not found", "severity": "minor", "description": msg})

    if found:
        return ("unverified" if any(d["severity"] != "minor" for d in discrepancies) else "verified"), discrepancies
    statuses = {p.get("status") for p in entries}
    if "not_found" in statuses:
        return "not_found", discrepancies
    if statuses == {"not_configured"}:
        return "not_configured", discrepancies
    return "pending", discrepancies


# ── Evidence for the job's skills (shown only; never scored) ───────

def _norm(skill: str) -> str:
    s = re.sub(r"[^a-z0-9+#]", "", skill.lower())
    return s[:-2] if s.endswith("js") and len(s) > 4 else s


def skill_evidence(entries: List[dict], required_skills: List[str]) -> List[dict]:
    """[{skill, sources}] for required skills shown in portfolio projects, skills or Stack Overflow tags."""
    shown = {}
    for p in entries or []:
        if p.get("status") != "found":
            continue
        tools = [t for proj in p.get("projects") or [] for t in proj.get("tools") or []]
        tags = [t.split("-")[0] for t in p.get("top_tags") or []] + list(p.get("top_tags") or [])
        for t in [*tools, *(p.get("skills") or []), *tags]:
            if isinstance(t, str) and _norm(t):
                shown.setdefault(_norm(t), set()).add(p["platform"])
    out = []
    for skill in required_skills or []:
        if isinstance(skill, str) and _norm(skill) in shown:
            out.append({"skill": skill, "sources": sorted(shown[_norm(skill)])})
    return out


def summary_line(entries: List[dict]) -> str:
    """One line per found source for the fact checker's candidate context."""
    parts = []
    for p in entries or []:
        if p.get("status") != "found":
            continue
        stats = []
        for key in ("name", "headline", "reputation", "followers", "appreciations", "competitions"):
            if p.get(key) is not None:
                stats.append(f"{key} {p[key]}")
        if p.get("badges"):
            stats.append("badges " + ", ".join(f"{v} {k}" for k, v in p["badges"].items()))
        if p.get("top_tags"):
            stats.append("top tags " + ", ".join(p["top_tags"]))
        if p.get("tiers"):
            stats.append("tiers " + ", ".join(f"{k} {v}" for k, v in p["tiers"].items()))
        if p.get("medals"):
            stats.append("medals " + ", ".join(f"{v} {k}" for k, v in p["medals"].items()))
        if p.get("projects"):
            stats.append("projects " + " / ".join(
                pr["title"] + (f" ({', '.join(pr['tools'])})" if pr.get("tools") else "") for pr in p["projects"][:5]))
        if p.get("skills"):
            stats.append("skills " + ", ".join(p["skills"][:10]))
        if p.get("experience"):
            stats.append("experience " + " / ".join(
                " ".join(filter(None, [e.get("role"), "at", e.get("organisation"), e.get("dates")])) for e in p["experience"][:4]))
        issues = p.get("issues") or []
        stats.append("mismatches: " + " / ".join(issues) if issues else "no mismatch with the resume")
        parts.append(f"{p['platform']} {p.get('handle')}: " + ", ".join(stats))
    return "; ".join(parts) or "None"
