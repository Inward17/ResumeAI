import textwrap
import langextract as lx


PARSER_PROMPT = textwrap.dedent("""
Extract structured resume information from the entire document.
Extract each field only ONCE from the complete resume.

IMPORTANT FOR PROJECTS EXTRACTION:
- Extract EACH project separately as individual project entries
- For each project, include: project name, technologies used, description, and duration/date if available

Return the following information:
- full_name: The candidate's full name
- email: Email address
- phone_number: Contact phone number
- github: GitHub profile URL
- linkedin: LinkedIn profile URL
- skills: All technical skills, languages, frameworks, and tools
- education: All education details including degree, university, year
- experience: All work experience including company, role, duration, and responsibilities
- projects: Extract EACH project separately with complete details
- certifications: All certifications with issuing organization
- achievements: All achievements, awards, or accomplishments
""")


EXAMPLES = [
    lx.data.ExampleData(
        text=textwrap.dedent("""
        John Doe
        Email: john.doe@gmail.com | Phone: +1 555-123-4567
        GitHub: github.com/johndoe | LinkedIn: linkedin.com/in/johndoe
        
        SKILLS: Python, FastAPI, Docker, React, MongoDB, JavaScript, Node.js, AWS
        
        EDUCATION
        B.Tech in Computer Science, MIT, 2020
        
        EXPERIENCE
        Software Engineer at Google (2020–2024)
        - Built scalable microservices
        - Led team of 5 developers
        
        PROJECTS
        E-commerce Platform (Jan 2023 - Mar 2023)
        Python, Flask, React, PostgreSQL
        - Built full-stack e-commerce application
        - Implemented payment gateway integration
        
        Task Management App (Apr 2023 - Jun 2023)
        React, Node.js, MongoDB, Express
        - Developed real-time collaboration features
        - Implemented drag-and-drop functionality
        
        CERTIFICATIONS
        AWS Certified Solutions Architect (Amazon)
        
        ACHIEVEMENTS
        - Won Best Innovation Award at TechHack 2023
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
            lx.data.Extraction(extraction_class="projects", extraction_text="E-commerce Platform (Jan 2023 - Mar 2023) - Python, Flask, React, PostgreSQL - Built full-stack e-commerce application - Implemented payment gateway integration"),
            lx.data.Extraction(extraction_class="projects", extraction_text="Task Management App (Apr 2023 - Jun 2023) - React, Node.js, MongoDB, Express - Developed real-time collaboration features - Implemented drag-and-drop functionality"),
            lx.data.Extraction(extraction_class="company", extraction_text="Google"),
            lx.data.Extraction(extraction_class="university", extraction_text="MIT"),
            lx.data.Extraction(extraction_class="certifications", extraction_text="AWS Certified Solutions Architect (Amazon)"),
            lx.data.Extraction(extraction_class="achievements", extraction_text="Won Best Innovation Award at TechHack 2023"),
        ]
    )
]