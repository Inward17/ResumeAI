"""AI review of a candidate's deployed projects (on demand, evidence only)."""
from app.services.project_reviews.discovery import all_projects, from_resume, select
from app.services.project_reviews.review import discrepancies, interview_context, summary_line

__all__ = ["all_projects", "from_resume", "select", "discrepancies", "interview_context", "summary_line"]
