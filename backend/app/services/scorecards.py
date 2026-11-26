"""
Structured interview scorecards: the per-job template, interviewer submissions and
the evidence summary. Pure logic (no database) so it is easy to test; the routes
are in app/routes/scorecard_routes.py.

Ratings are 1-4 against behavioural anchors; a competency can be "not assessed"
(rating None). Scores reach the UI as 0-100 and None means "not available".
"""
import re
import secrets
from statistics import mean
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.utils.text_utils import as_data

MIN_EVIDENCE_CHARS = 20
RECOMMENDATIONS = ("strong_no", "no", "yes", "strong_yes")
_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


# ── Template ─────────────────────────────────────────────────────────────

class Competency(BaseModel):
    id: str = Field("", validate_default=True)
    name: str = Field(min_length=1, max_length=80)
    description: str = Field("", max_length=500)
    # What a 1, 2, 3 and 4 look like, in that order
    anchors: List[str] = Field(default_factory=lambda: ["", "", "", ""])
    weight: int = Field(1, ge=1, le=10)

    @field_validator("name", "description")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("anchors")
    @classmethod
    def _four_anchors(cls, v: List[str]) -> List[str]:
        if len(v) != 4:
            raise ValueError("anchors must describe ratings 1, 2, 3 and 4")
        if any(not isinstance(a, str) or len(a) > 300 for a in v):
            raise ValueError("each anchor is text of at most 300 characters")
        return [a.strip() for a in v]

    @field_validator("id")
    @classmethod
    def _valid_id(cls, v: str) -> str:
        v = (v or "").strip()
        if v and not _ID.match(v):
            raise ValueError("id may only contain letters, digits, - and _")
        return v or secrets.token_hex(4)


class TemplateIn(BaseModel):
    competencies: List[Competency] = Field(min_length=3, max_length=8)

    @model_validator(mode="after")
    def _unique(self):
        names = [c.name.lower() for c in self.competencies]
        if not all(names):
            raise ValueError("every competency needs a name")
        if len(set(names)) != len(names):
            raise ValueError("competency names must be different")
        ids = [c.id for c in self.competencies]
        if len(set(ids)) != len(ids):
            raise ValueError("competency ids must be different")
        return self


# ── Submission ───────────────────────────────────────────────────────────

class RatingIn(BaseModel):
    competency_id: str = Field(min_length=1, max_length=40)
    rating: Optional[int] = Field(None, ge=1, le=4)  # None = not assessed
    evidence: str = Field("", max_length=2000)
    # Interview questions (from the tag evaluation) the candidate answered on this
    question_ids: List[int] = Field(default_factory=list, max_length=20)


class ScorecardIn(BaseModel):
    ratings: List[RatingIn] = Field(default_factory=list, max_length=8)
    recommendation: Optional[Literal["strong_no", "no", "yes", "strong_yes"]] = None
    summary: str = Field("", max_length=4000)
    submit: bool = False


def check_submission(template: List[dict], body: ScorecardIn) -> List[dict]:
    """The ratings to store, in template order. Raises ValueError with a message for the user.

    Drafts may be incomplete; a submission needs at least one rating, an evidence
    note of MIN_EVIDENCE_CHARS for every rated competency, a recommendation and a summary.
    """
    known = {c["id"]: c for c in template}
    given = {}
    for r in body.ratings:
        if r.competency_id not in known:
            raise ValueError("A rating refers to a competency that isn't on this job's scorecard")
        if r.competency_id in given:
            raise ValueError("Each competency can be rated once")
        given[r.competency_id] = r
    ratings = [
        {"competency_id": cid, "rating": given[cid].rating, "evidence": given[cid].evidence.strip(),
         "question_ids": sorted(set(given[cid].question_ids))}
        for cid in known if cid in given
    ]
    if not body.submit:
        return ratings
    rated = [r for r in ratings if r["rating"] is not None]
    if not rated:
        raise ValueError("Rate at least one competency before submitting")
    thin = [known[r["competency_id"]]["name"] for r in rated if len(r["evidence"]) < MIN_EVIDENCE_CHARS]
    if thin:
        raise ValueError(f"Add evidence (what the candidate said or did, at least {MIN_EVIDENCE_CHARS} "
                         f"characters) for: {', '.join(thin)}")
    if not body.recommendation:
        raise ValueError("Choose an overall recommendation")
    if not body.summary.strip():
        raise ValueError("Write a short summary")
    return ratings


# ── Independent review ───────────────────────────────────────────────────

def must_submit_first(own_card: Optional[dict]) -> bool:
    """True while the caller owes a scorecard for this candidate (asked to, or started one).

    They then see only their own until they submit, so others' ratings can't anchor theirs.
    Anyone who hasn't been asked to interview (owners, recruiters) sees every submitted card.
    """
    return bool(own_card) and own_card.get("status") != "submitted"


# ── Evidence summary ─────────────────────────────────────────────────────

def to_100(rating: Optional[float]) -> Optional[int]:
    """1-4 → 0-100 (1 = 0, 4 = 100); None stays None."""
    return None if rating is None else round((rating - 1) / 3 * 100)


def aggregate(template: List[dict], cards: List[dict], evaluation: Optional[dict] = None) -> dict:
    """Per-competency mean, spread and disagreement, weighted overall 0-100, recommendation counts,
    and every evidence note grouped by competency. Only submitted cards count."""
    cards = [c for c in cards if c.get("status") == "submitted"]
    questions = {q.get("question_id"): q for q in (evaluation or {}).get("questions", [])}
    competencies, weighted, weights = [], 0.0, 0
    for comp in template:
        notes, values = [], []
        for card in cards:
            r = next((x for x in card.get("ratings", []) if x.get("competency_id") == comp["id"]), None)
            if not r or (r.get("rating") is None and not r.get("evidence")):
                continue
            if r.get("rating") is not None:
                values.append(r["rating"])
            notes.append({
                "author": card.get("author_name"), "author_uid": card.get("author_uid"),
                "date": card.get("submitted_at"), "rating": r.get("rating"), "evidence": r.get("evidence", ""),
                "questions": [{"id": qid, "question": questions[qid].get("question"),
                               "covered": questions[qid].get("selected_tags", []),
                               "total": questions[qid].get("total_tags")}
                              for qid in r.get("question_ids", []) if qid in questions],
            })
        avg = mean(values) if values else None
        spread = (max(values) - min(values)) if values else None
        if avg is not None:
            weighted += avg * comp["weight"]
            weights += comp["weight"]
        competencies.append({
            "id": comp["id"], "name": comp["name"], "weight": comp["weight"],
            "mean": None if avg is None else round(avg, 2), "score": to_100(avg),
            "spread": spread, "ratings": len(values),
            "disagreement": spread is not None and spread >= 2,
            "evidence": notes,
        })
    counts = {k: 0 for k in RECOMMENDATIONS}
    for card in cards:
        if card.get("recommendation") in counts:
            counts[card["recommendation"]] += 1
    return {
        "submitted": len(cards),
        # Weighted over the competencies someone rated; None when nobody rated anything
        "overall_score": to_100(weighted / weights) if weights else None,
        "recommendations": counts,
        "competencies": competencies,
        "summaries": [{"author": c.get("author_name"), "date": c.get("submitted_at"),
                       "recommendation": c.get("recommendation"), "summary": c.get("summary", "")} for c in cards],
    }


# ── AI prompts ───────────────────────────────────────────────────────────

SUGGEST_SYSTEM = """You design structured interview scorecards.
From the job description and skills, propose 4 to 6 competencies an interviewer can assess in
conversation. For each give a short name, a one-sentence description, behavioural anchors for
ratings 1 (clear gap), 2 (some evidence, below the bar), 3 (meets the bar) and 4 (strong,
above the bar) describing what the candidate would say or do, and a weight from 1 to 5 by
importance to the job. Judge job-related skills and behaviours only: never age, gender,
nationality, family, health or other protected characteristics.
Return ONLY JSON: {"competencies": [{"name": "", "description": "", "anchors": ["", "", "", ""], "weight": 3}]}"""


def suggest_prompt(job: dict) -> str:
    return (f"Job title: {as_data(job.get('job_title', ''))}\n"
            f"Required skills: {as_data(', '.join(job.get('required_skills') or []))}\n"
            f"Preferred skills: {as_data(', '.join(job.get('preferred_skills') or []))}\n"
            f"Job description:\n{as_data((job.get('job_description') or '')[:6000])}")


BRIEF_SYSTEM = """You summarise interviewers' submitted scorecard notes for a hiring decision.
Use ONLY the notes given. Do not add facts, opinions, or claims about the candidate that no
interviewer wrote, and do not judge anything the notes don't cover. Cite the interviewer
labels (I1, I2, ...) behind every point. Point out where interviewers disagree.
Return ONLY JSON: {"summary": "2-4 sentences", "points": [{"competency": "<name>", "text": "", "cited": ["I1"]}]}"""


def brief_prompt(template: List[dict], cards: List[dict]) -> tuple:
    """(prompt, {label: author name}). Interviewers are sent as I1, I2... rather than by name."""
    names = {c["id"]: c["name"] for c in template}
    labels, lines = {}, []
    for i, card in enumerate([c for c in cards if c.get("status") == "submitted"], 1):
        label = f"I{i}"
        labels[label] = card.get("author_name") or "Interviewer"
        lines.append(f"[{label}] recommendation: {card.get('recommendation')}; summary: {card.get('summary', '')}")
        for r in card.get("ratings", []):
            if r.get("competency_id") in names and (r.get("rating") is not None or r.get("evidence")):
                rating = r["rating"] if r.get("rating") is not None else "not assessed"
                lines.append(f"[{label}] {names[r['competency_id']]} rated {rating}/4: {r.get('evidence', '')}")
    return f"Interviewer notes:\n{as_data(chr(10).join(lines))}", labels


def check_brief(data, labels: Dict[str, str]) -> Optional[dict]:
    """The model's brief with labels turned back into names, or None if it isn't usable."""
    if not isinstance(data, dict) or not isinstance(data.get("summary"), str) or not data["summary"].strip():
        return None
    points = []
    for p in data.get("points") or []:
        if not isinstance(p, dict) or not isinstance(p.get("text"), str) or not p["text"].strip():
            continue
        cited = [labels[c] for c in (p.get("cited") or []) if isinstance(c, str) and c in labels]
        if not cited:  # an uncited point isn't backed by any note
            continue
        points.append({"competency": str(p.get("competency") or "")[:80], "text": p["text"].strip()[:600], "cited": cited})
    return {"summary": data["summary"].strip()[:1200], "points": points[:12]}


if __name__ == "__main__":
    tpl = [{"id": "a", "name": "A", "weight": 3}, {"id": "b", "name": "B", "weight": 1}]
    cards = [{"status": "submitted", "ratings": [{"competency_id": "a", "rating": 4, "evidence": "x"}], "recommendation": "yes"},
             {"status": "submitted", "ratings": [{"competency_id": "a", "rating": 2, "evidence": "y"},
                                                 {"competency_id": "b", "rating": 1, "evidence": "z"}]}]
    s = aggregate(tpl, cards)
    assert s["competencies"][0]["mean"] == 3 and s["competencies"][0]["disagreement"] is True
    assert s["overall_score"] == round(((3 * 3 + 1 * 1) / 4 - 1) / 3 * 100)
    assert aggregate(tpl, [])["overall_score"] is None
    print("scorecards self-check OK")
