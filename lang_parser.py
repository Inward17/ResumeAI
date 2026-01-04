import langextract as lx
import textwrap
import pdfplumber
import docx
import json
import os
import glob
import re
from dotenv import load_dotenv 

# Load environment variables from .env file
load_dotenv()

# ---------- CONFIG ----------
MODEL_ID = "gemini-2.5-flash"
API_KEY = os.getenv("API_KEY") 
# ----------------------------

def read_pdf(file_path):
    with pdfplumber.open(file_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)

def read_docx(file_path):
    doc = docx.Document(file_path)
    return "\n".join(p.text for p in doc.paragraphs)

def read_file(file_path):
    ext = file_path.lower().split(".")[-1]
    if ext == "pdf":
        return read_pdf(file_path)
    elif ext == "docx":
        return read_docx(file_path)
    elif ext == "txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file format: {ext}")

# ---------- IMPROVED PROMPT WITH PROJECT-SPECIFIC INSTRUCTIONS ----------
prompt = textwrap.dedent("""
Extract structured resume information from the entire document.
Extract each field only ONCE from the complete resume.

IMPORTANT FOR PROJECTS EXTRACTION:
- Extract EACH project separately as individual project entries
- For each project, include: project name, technologies used, description, and duration/date if available
- If there are multiple projects, extract each one as a separate projects entry
- Preserve all details for each individual project

Return the following information:
- full_name: The candidate's full name
- email: Email address
- phone_number: Contact phone number
- github: GitHub profile URL
- linkedin: LinkedIn profile URL
- skills: All technical skills, languages, frameworks, and tools (as a comma-separated list)
- education: All education details including degree, university, year
- experience: All work experience including company, role, duration, and responsibilities
- projects: Extract EACH project separately with complete details including project name, technologies used, description, and duration
- certifications: All certifications with issuing organization
- achievements: All achievements, awards, or accomplishments
""")

# ---------- UPDATED EXAMPLES WITH MULTIPLE PROJECTS ----------
examples = [
    lx.data.ExampleData(
        text=textwrap.dedent("""
        John Doe
        Email: john.doe@gmail.com
        Phone: +1 555-123-4567
        GitHub: github.com/johndoe
        LinkedIn: linkedin.com/in/johndoe
        
        SKILLS
        Python, FastAPI, Docker, React, MongoDB, JavaScript, Node.js, AWS
        
        EDUCATION
        B.Tech in Computer Science, MIT, 2020
        
        EXPERIENCE
        Software Engineer at Google (2020–2024)
        - Built scalable microservices
        - Led team of 5 developers
        
        PROJECTS
        E-commerce Platform (Jan 2023 - Mar 2023)
        Python, Flask, React, PostgreSQL
        - Built a full-stack e-commerce application
        - Implemented payment gateway integration
        - Deployed on AWS EC2
        
        Task Management App (Apr 2023 - Jun 2023)
        React, Node.js, MongoDB, Express
        - Developed real-time collaboration features
        - Implemented drag-and-drop functionality
        
        Weather Dashboard (Jul 2023)
        JavaScript, HTML, CSS, OpenWeather API
        - Created responsive weather application
        - Implemented location-based forecasts
        
        Portfolio Website (Aug 2023)
        React, CSS, Netlify
        - Built personal portfolio with project showcase
        - Optimized for mobile devices
        
        CERTIFICATIONS
        AWS Certified Solutions Architect (Amazon)
        Docker Certified Associate (Docker Inc.)
        
        ACHIEVEMENTS
        - Won Best Innovation Award at TechHack 2023
        - Published research paper in IEEE Conference
        """),
        extractions=[
            lx.data.Extraction(extraction_class="full_name", extraction_text="John Doe"),
            lx.data.Extraction(extraction_class="email", extraction_text="john.doe@gmail.com"),
            lx.data.Extraction(extraction_class="phone_number", extraction_text="+1 555-123-4567"),
            lx.data.Extraction(extraction_class="github", extraction_text="github.com/johndoe"),
            lx.data.Extraction(extraction_class="linkedin", extraction_text="linkedin.com/in/johndoe"),
            lx.data.Extraction(extraction_class="skills", extraction_text="Python, FastAPI, Docker, React, MongoDB, JavaScript, Node.js, AWS"),
            lx.data.Extraction(extraction_class="education", extraction_text="B.Tech in Computer Science, MIT, 2020"),
            lx.data.Extraction(extraction_class="experience", extraction_text="Software Engineer at Google (2020–2024) - Built scalable microservices - Led team of 5 developers"),
            
            # Multiple project extractions - ONE PER PROJECT
            lx.data.Extraction(extraction_class="projects", extraction_text="E-commerce Platform (Jan 2023 - Mar 2023) - Python, Flask, React, PostgreSQL - Built a full-stack e-commerce application - Implemented payment gateway integration - Deployed on AWS EC2"),
            lx.data.Extraction(extraction_class="projects", extraction_text="Task Management App (Apr 2023 - Jun 2023) - React, Node.js, MongoDB, Express - Developed real-time collaboration features - Implemented drag-and-drop functionality"),
            lx.data.Extraction(extraction_class="projects", extraction_text="Weather Dashboard (Jul 2023) - JavaScript, HTML, CSS, OpenWeather API - Created responsive weather application - Implemented location-based forecasts"),
            lx.data.Extraction(extraction_class="projects", extraction_text="Portfolio Website (Aug 2023) - React, CSS, Netlify - Built personal portfolio with project showcase - Optimized for mobile devices"),
            
            lx.data.Extraction(extraction_class="certifications", extraction_text="AWS Certified Solutions Architect (Amazon), Docker Certified Associate (Docker Inc.)"),
            lx.data.Extraction(extraction_class="achievements", extraction_text="Won Best Innovation Award at TechHack 2023, Published research paper in IEEE Conference"),
        ]
    )
]

def parse_projects_from_extractions(extractions):
    """Parse and organize multiple project extractions into structured format"""
    projects = []
    
    # Get all project extractions
    project_extractions = [ext for ext in extractions if ext.extraction_class == "projects"]
    
    for project_ext in project_extractions:
        project_text = project_ext.extraction_text.strip()
        if not project_text:
            continue
            
        # Basic parsing of project details (you can enhance this based on your needs)
        project_data = {
            "name": "",
            "technologies": [],
            "description": "",
            "duration": "",
            "details": project_text
        }
        
        # Simple parsing logic - you can enhance this based on your resume format
        lines = [line.strip() for line in project_text.split('-') if line.strip()]
        
        if lines:
            # First line typically contains project name and possibly duration
            first_line = lines[0]
            
            # Extract duration if present in parentheses
            duration_match = re.search(r'\((.*?)\)', first_line)
            if duration_match:
                project_data["duration"] = duration_match.group(1)
                project_data["name"] = first_line.split('(')[0].strip()
            else:
                project_data["name"] = first_line
            
            # Look for technology keywords in the project text
            tech_keywords = ["Python", "JavaScript", "React", "Node.js", "Java", "C++", "AWS", "Docker", 
                           "MongoDB", "PostgreSQL", "MySQL", "Flask", "Django", "FastAPI", "HTML", "CSS",
                           "TypeScript", "Vue", "Angular", "Express", "Spring", "TensorFlow", "PyTorch"]
            
            found_tech = []
            for tech in tech_keywords:
                if tech.lower() in project_text.lower():
                    found_tech.append(tech)
            
            if found_tech:
                project_data["technologies"] = found_tech
            
            # Use the rest as description
            if len(lines) > 1:
                project_data["description"] = " - ".join(lines[1:])
        
        projects.append(project_data)
    
    return projects

def extract_single_resume(file_path):
    """Extract data from a single resume file"""
    try:
        print(f"📖 Processing: {os.path.basename(file_path)}")
        text = read_file(file_path)
        
        result = lx.extract(
            text_or_documents=text,
            prompt_description=prompt,
            examples=examples,
            model_id=MODEL_ID,
            api_key=API_KEY,
        )
        
        # Group extractions by class and filter out empty ones
        grouped_data = {
            "full_name": "",
            "email": "",
            "phone_number": "",
            "github": "",
            "linkedin": "",
            "skills": [],
            "education": [],
            "experience": [],
            "projects": [],
            "certifications": [],
            "achievements": []
        }
        
        for ext in result.extractions:
            extraction_class = ext.extraction_class
            extraction_text = ext.extraction_text.strip()
            
            # Skip empty extractions
            if not extraction_text:
                continue
            
            # For single-value fields, take the first non-empty value
            if extraction_class in ["full_name", "email", "phone_number", "github", "linkedin"]:
                if not grouped_data[extraction_class]:
                    grouped_data[extraction_class] = extraction_text
            
            # For multi-value fields, collect all non-empty values
            elif extraction_class == "skills":
                if extraction_text not in grouped_data["skills"]:
                    grouped_data["skills"].append(extraction_text)
            
            elif extraction_class == "education":
                if extraction_text not in grouped_data["education"]:
                    grouped_data["education"].append(extraction_text)
            
            elif extraction_class == "experience":
                if extraction_text not in grouped_data["experience"]:
                    grouped_data["experience"].append(extraction_text)
            
            elif extraction_class == "projects":
                if extraction_text not in grouped_data["projects"]:
                    grouped_data["projects"].append(extraction_text)
            
            elif extraction_class == "certifications":
                if extraction_text not in grouped_data["certifications"]:
                    grouped_data["certifications"].append(extraction_text)
            
            elif extraction_class == "achievements":
                if extraction_text not in grouped_data["achievements"]:
                    grouped_data["achievements"].append(extraction_text)
        
        # Process projects separately to extract structured information
        structured_projects = parse_projects_from_extractions(result.extractions)
        
        # Flatten skills into a single string if needed
        if grouped_data["skills"]:
            grouped_data["skills"] = ", ".join(grouped_data["skills"])
        else:
            grouped_data["skills"] = None
        
        # Create final structured output with null for empty fields
        extracted_data = {
            "personal_info": {
                "full_name": grouped_data["full_name"] if grouped_data["full_name"] else None,
                "email": grouped_data["email"] if grouped_data["email"] else None,
                "phone_number": grouped_data["phone_number"] if grouped_data["phone_number"] else None,
                "github": grouped_data["github"] if grouped_data["github"] else None,
                "linkedin": grouped_data["linkedin"] if grouped_data["linkedin"] else None
            },
            "skills": grouped_data["skills"],
            "education": grouped_data["education"] if grouped_data["education"] else None,
            "experience": grouped_data["experience"] if grouped_data["experience"] else None,
            "projects": structured_projects if structured_projects else None,  # Use structured projects
            "certifications": grouped_data["certifications"] if grouped_data["certifications"] else None,
            "achievements": grouped_data["achievements"] if grouped_data["achievements"] else None,
            "raw_project_count": len(grouped_data["projects"])  # For debugging
        }
        
        # Write JSON to file
        output_file = os.path.splitext(file_path)[0] + "_data.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(extracted_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Extraction Complete for: {os.path.basename(file_path)}")
        print(f"📄 Projects found: {len(structured_projects)}")
        print(f"📄 Saved to: {output_file}")
        
        return extracted_data
        
    except Exception as e:
        print(f"❌ Error processing {file_path}: {str(e)}")
        return None

def extract_multiple_resumes(file_paths):
    """Extract data from multiple resume files sequentially"""
    all_results = {}
    
    print(f"🚀 Starting sequential processing of {len(file_paths)} files...")
    print("=" * 50)
    
    for i, file_path in enumerate(file_paths, 1):
        print(f"\n📋 Processing file {i}/{len(file_paths)}")
        
        result = extract_single_resume(file_path)
        if result:
            all_results[file_path] = result
            project_count = len(result.get('projects', [])) if result.get('projects') else 0
            print(f"📊 Extracted {project_count} projects")
        else:
            all_results[file_path] = {"error": "Failed to process file"}
        
        print("-" * 30)
    
    successful = len([r for r in all_results.values() if 'error' not in r])
    total_projects = sum(len(r.get('projects', [])) for r in all_results.values() if 'projects' in r and r['projects'])
    
    print(f"\n🎉 All files processed! Successfully extracted: {successful}/{len(file_paths)}")
    print(f"📊 Total projects extracted: {total_projects}")
    
    return all_results

def get_resume_files(directory_path=None, file_patterns=None):
    """Get all resume files from directory or specific file patterns"""
    if directory_path:
        # Get all supported files from directory
        patterns = ["*.pdf", "*.docx", "*.txt"]
        files = []
        for pattern in patterns:
            files.extend(glob.glob(os.path.join(directory_path, pattern)))
        return sorted(files)
    
    elif file_patterns:
        # Get specific files matching patterns
        files = []
        for pattern in file_patterns:
            files.extend(glob.glob(pattern))
        return sorted(files)
    
    else:
        return []

if __name__ == "__main__":
    # Option 1: Process all files in a directory
    resumes_directory = "resumes"  # Change this to your directory path
    resume_files = get_resume_files(directory_path=resumes_directory)
    
    # Option 2: Process specific files using patterns
    # resume_files = get_resume_files(file_patterns=["resume1.pdf", "resume2.docx", "*.pdf"])
    
    # Option 3: Manually specify file list
    # resume_files = ["resume1.pdf", "resume2.docx", "resume3.txt"]
    
    if not resume_files:
        print("❌ No resume files found!")
        print("Please either:")
        print("1. Set 'resumes_directory' to a folder containing resume files")
        print("2. Use file_patterns to specify file patterns")
        print("3. Manually specify resume_files list")
    else:
        print(f"📁 Found {len(resume_files)} resume files:")
        for file in resume_files:
            print(f"   - {file}")
        
        # Process all files sequentially
        all_results = extract_multiple_resumes(resume_files)
        
        # Optional: Save combined results to a single file
        combined_output = "all_resumes_data.json"
        with open(combined_output, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n📊 Combined results saved to: {combined_output}")