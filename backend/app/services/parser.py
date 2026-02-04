import re
import asyncio
import langextract as lx
from app.utils.prompts import PARSER_PROMPT, EXAMPLES
import os


def parse_projects(extractions):
    """Parse project extractions into structured format"""
    projects = []
    project_extractions = [ext for ext in extractions if ext.extraction_class == "projects"]
    
    for project_ext in project_extractions:
        text = project_ext.extraction_text.strip()
        if not text:
            continue
        
        project = {
            "name": "",
            "technologies": [],
            "description": "",
            "duration": "",
            "details": text
        }
        
        lines = [line.strip() for line in text.split('-') if line.strip()]
        if lines:
            first_line = lines[0]
            duration_match = re.search(r'\((.*?)\)', first_line)
            
            if duration_match:
                project["duration"] = duration_match.group(1)
                project["name"] = first_line.split('(')[0].strip()
            else:
                project["name"] = first_line
            
            # Extract technologies
            tech_keywords = [
                "Python", "JavaScript", "React", "Node.js", "Java", "C++", "AWS", "Docker",
                "MongoDB", "PostgreSQL", "MySQL", "Flask", "Django", "FastAPI", "HTML", "CSS",
                "TypeScript", "Vue", "Angular", "Express", "Spring", "TensorFlow", "PyTorch"
            ]
            project["technologies"] = [tech for tech in tech_keywords if tech.lower() in text.lower()]
            
            if len(lines) > 1:
                project["description"] = " - ".join(lines[1:])
        
        projects.append(project)
    
    return projects


async def parse_resume(text: str) -> dict:
    """Parse resume text and extract structured information"""
    
    # Get API key from env
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    # Run langextract in thread (blocking call)
    result = await asyncio.to_thread(
        lx.extract,
        text_or_documents=text,
        prompt_description=PARSER_PROMPT,
        examples=EXAMPLES,
        model_id="gemini-2.5-flash",
        api_key=GEMINI_API_KEY,
    )
    
    # Group extractions
    data = {
        "full_name": "", "email": "", "phone_number": "", "github": "", "linkedin": "",
        "skills": [], "education": [], "experience": [], "projects": [],
        "certifications": [], "achievements": [],
        "university": [], "company": []  # NEW: For verification
    }
    
    for ext in result.extractions:
        cls = ext.extraction_class
        txt = ext.extraction_text.strip()
        if not txt:
            continue
        
        if cls in ["full_name", "email", "phone_number", "github", "linkedin"]:
            if not data[cls]:
                data[cls] = txt
        elif cls in data:  # Only append if key exists in data dict
            if txt not in data[cls]:
                data[cls].append(txt)
    
    # Parse projects
    structured_projects = parse_projects(result.extractions)
    
    # Build output
    return {
        "personal_info": {
            "full_name": data["full_name"] or None,
            "email": data["email"] or None,
            "phone_number": data["phone_number"] or None,
            "github": data["github"] or None,
            "linkedin": data["linkedin"] or None
        },
        "skills": ", ".join(data["skills"]) if data["skills"] else None,
        "education": data["education"] if data["education"] else None,
        "experience": data["experience"] if data["experience"] else None,
        "projects": structured_projects if structured_projects else None,
        "certifications": data["certifications"] if data["certifications"] else None,
        "achievements": data["achievements"] if data["achievements"] else None,
        # NEW: Extracted entity names for verification
        "university": data["university"] if data["university"] else None,
        "company": data["company"] if data["company"] else None,
    }