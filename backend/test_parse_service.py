r"""
test_parse_service.py
---------------------
Temporary service to test resume parsing using the same
langextract + Gemini setup the real app uses.

USAGE (from the backend/ folder with venv active):

    # Parse a single file
    python test_parse_service.py resumes\Soham_Miniyar_Resume.pdf

    # Parse multiple files
    python test_parse_service.py resumes\Soham_Miniyar_Resume.pdf resumes\Rohan_Mohite.pdf

    # Parse all resumes in a folder
    python test_parse_service.py --dir resumes\

    # Add delay between calls to avoid rate limits
    python test_parse_service.py --dir resumes\ --delay 5
"""

import os
import sys
import time
import json
import argparse
import textwrap
import pdfplumber
import docx as _docx
import langextract as lx
from pathlib import Path
from dotenv import load_dotenv

# ── Load env ──────────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("LANGEXTRACT_API_KEY")
MODEL_ID       = os.getenv("LANGEXTRACT_MODEL_ID") or os.getenv("MODEL_ID") or "gemini-2.0-flash"

if not GEMINI_API_KEY:
    print("❌  No API key found. Set GEMINI_API_KEY in .env")
    sys.exit(1)

# ── Prompt (same as real parser) ──────────────────────────────────────────────
PARSER_PROMPT = textwrap.dedent("""
Extract structured resume information from the entire document.
Extract each field only ONCE from the complete resume.
Return the following information:
- full_name: The candidate's full name
- email: Email address
- phone_number: Contact phone number
- github: GitHub profile URL
- linkedin: LinkedIn profile URL
- skills: All technical skills, languages, frameworks, and tools (as a comma-separated list)
- education: All education details including degree, university, year
- experience: All work experience including company, role, duration, and responsibilities
- projects: All project details including project name, technologies used, and description
- certifications: All certifications with issuing organization
- achievements: All achievements, awards, or accomplishments
""")

EXAMPLES = [
    lx.data.ExampleData(
        text=textwrap.dedent("""
        John Doe
        Email: john.doe@gmail.com | Phone: +1 555-123-4567
        GitHub: github.com/johndoe | LinkedIn: linkedin.com/in/johndoe

        SKILLS: Python, FastAPI, Docker, React, MongoDB

        EDUCATION: B.Tech in Computer Science, MIT, 2020

        EXPERIENCE
        Software Engineer at Google (2020–2024)
        - Built scalable microservices

        PROJECTS
        E-commerce Platform | Python, Flask, React
        - Built a full-stack e-commerce application

        CERTIFICATIONS: AWS Certified Solutions Architect (Amazon)
        ACHIEVEMENTS: Won Best Innovation Award at TechHack 2023
        """),
        extractions=[
            lx.data.Extraction(extraction_class="full_name",      extraction_text="John Doe"),
            lx.data.Extraction(extraction_class="email",          extraction_text="john.doe@gmail.com"),
            lx.data.Extraction(extraction_class="phone_number",   extraction_text="+1 555-123-4567"),
            lx.data.Extraction(extraction_class="github",         extraction_text="github.com/johndoe"),
            lx.data.Extraction(extraction_class="linkedin",       extraction_text="linkedin.com/in/johndoe"),
            lx.data.Extraction(extraction_class="skills",         extraction_text="Python, FastAPI, Docker, React, MongoDB"),
            lx.data.Extraction(extraction_class="education",      extraction_text="B.Tech in Computer Science, MIT, 2020"),
            lx.data.Extraction(extraction_class="experience",     extraction_text="Software Engineer at Google (2020-2024) - Built scalable microservices"),
            lx.data.Extraction(extraction_class="projects",       extraction_text="E-commerce Platform | Python, Flask, React - Built a full-stack e-commerce application"),
            lx.data.Extraction(extraction_class="certifications", extraction_text="AWS Certified Solutions Architect (Amazon)"),
            lx.data.Extraction(extraction_class="achievements",   extraction_text="Won Best Innovation Award at TechHack 2023"),
        ]
    )
]

# ── File readers ──────────────────────────────────────────────────────────────
def read_file(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        pages = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or " ".join(
                    w.get("text", "") for w in page.extract_words()
                )
                pages.append(text)
        return "\n\n".join(pages)
    elif ext == ".docx":
        doc = _docx.Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    elif ext == ".txt":
        return Path(path).read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unsupported file type: {ext}")

# ── Group extractions (same logic as real parser) ─────────────────────────────
def group_extractions(result) -> dict:
    data = {
        "full_name": "", "email": "", "phone_number": "", "github": "", "linkedin": "",
        "skills": [], "education": [], "experience": [], "projects": [],
        "certifications": [], "achievements": [],
    }
    for ext in result.extractions:
        cls = getattr(ext, "extraction_class", None)
        txt = (getattr(ext, "extraction_text", "") or "").strip()
        if not txt:
            continue
        if cls in ["full_name", "email", "phone_number", "github", "linkedin"]:
            if not data[cls]:
                data[cls] = txt
        elif cls in data:
            if txt not in data[cls]:
                data[cls].append(txt)

    return {
        "personal_info": {
            "full_name":    data["full_name"]    or None,
            "email":        data["email"]        or None,
            "phone_number": data["phone_number"] or None,
            "github":       data["github"]       or None,
            "linkedin":     data["linkedin"]     or None,
        },
        "skills":         ", ".join(data["skills"])  if data["skills"]         else None,
        "education":      data["education"]           if data["education"]      else None,
        "experience":     data["experience"]          if data["experience"]     else None,
        "projects":       data["projects"]            if data["projects"]       else None,
        "certifications": data["certifications"]      if data["certifications"] else None,
        "achievements":   data["achievements"]        if data["achievements"]   else None,
    }

# ── Parse one file ────────────────────────────────────────────────────────────
def parse(file_path: str):
    fname = Path(file_path).name
    print(f"\n{'─'*58}")
    print(f"📄  {fname}")
    print(f"{'─'*58}")

    # Read text
    try:
        text = read_file(file_path)
        print(f"    Text extracted  : {len(text):,} characters")
    except Exception as e:
        print(f"    ❌  Read error  : {e}")
        return

    # Call langextract (same as the actual app)
    print(f"    Calling model   : {MODEL_ID} ...")
    t0 = time.time()
    try:
        result = lx.extract(
            text_or_documents=text,
            prompt_description=PARSER_PROMPT,
            examples=EXAMPLES,
            model_id=MODEL_ID,
            api_key=GEMINI_API_KEY,
        )
        elapsed = round(time.time() - t0, 2)
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        err = str(e)
        if "429" in err or "quota" in err.lower() or "rate" in err.lower():
            print(f"    ⚠️   RATE LIMIT HIT (429) — after {elapsed}s")
            print(f"         Tip: re-run with a longer --delay value")
        else:
            print(f"    ❌  API error ({elapsed}s): {err[:200]}")
        return

    # Token usage — check result object for any usage_metadata
    usage = getattr(result, "usage_metadata", None) or getattr(result, "token_usage", None)
    print(f"    ✅  Done in {elapsed}s")
    if usage:
        p = getattr(usage, "prompt_token_count",     getattr(usage, "prompt_tokens",   "—"))
        r = getattr(usage, "candidates_token_count", getattr(usage, "output_tokens",   "—"))
        t = getattr(usage, "total_token_count",      getattr(usage, "total_tokens",    "—"))
        print(f"    Tokens → prompt: {p}  |  response: {r}  |  total: {t}")
    else:
        print(f"    Token usage     : check AI Studio → https://aistudio.google.com/app/apikey")

    # Group and display
    parsed = group_extractions(result)
    print(f"\n    Parsed Result:")
    print(json.dumps(parsed, indent=6, ensure_ascii=False))

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description="Test resume parsing — rate limit & token usage checker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("files", nargs="*", help="Resume file path(s) to parse (pdf / docx / txt)")
    ap.add_argument("--dir",   help="Parse all resumes in this folder")
    ap.add_argument("--delay", type=float, default=2.0,
                    help="Seconds to wait between API calls (default: 2)")
    args = ap.parse_args()

    # Collect target files
    if args.dir:
        folder = Path(args.dir)
        all_files = sorted(
            f for f in folder.iterdir()
            if f.suffix.lower() in {".pdf", ".docx", ".txt"}
        )
        if not all_files:
            print(f"❌  No resume files found in: {folder}")
            sys.exit(1)
    elif args.files:
        all_files = [Path(f) for f in args.files]
    else:
        ap.print_help()
        sys.exit(0)

    print(f"\n{'='*58}")
    print(f"  Resume Parse Test  |  model: {MODEL_ID}")
    print(f"  Files to process  : {len(all_files)}")
    print(f"  Delay between calls: {args.delay}s")
    print(f"{'='*58}")

    for i, fp in enumerate(all_files):
        parse(str(fp))
        if i < len(all_files) - 1:
            print(f"\n    ⏳  Waiting {args.delay}s before next call ...")
            time.sleep(args.delay)

    print(f"\n{'='*58}")
    print(f"  Done!")
    print(f"  Full API usage → https://aistudio.google.com/app/apikey")
    print(f"{'='*58}\n")

if __name__ == "__main__":
    main()
