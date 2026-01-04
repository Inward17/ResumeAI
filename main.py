import os
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import List

# Import the function from your script
# Make sure your script is named parser.py
try:
    from lang_parser import extract_single_resume
except ImportError:
    print("="*50)
    print("ERROR: Could not import 'extract_single_resume' from parser.py")
    print("Please make sure your resume script is saved as 'parser.py' in the same directory.")
    print("="*50)
    exit()


# Load environment variables
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase URL and Key must be set in .env file")

# Initialize FastAPI app
app = FastAPI(title="Resume Parser API")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Add CORS middleware
# This allows your React frontend (on a different port) to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for simplicity (you can restrict to "http://localhost:3000")
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Resume Parser API is running"}


@app.post("/upload-resumes/")
async def upload_resumes(files: List[UploadFile] = File(...)):
    """
    Uploads one or more resume files, parses them, and saves to Supabase.
    """
    success_files = []
    errors = []

    for file in files:
        # Your parser.py script needs a file *path* to work.
        # So, we save the uploaded file to a temporary location.
        try:
            # Use a NamedTemporaryFile to handle temp file creation and cleanup
            with tempfile.NamedTemporaryFile(delete=False, suffix=file.filename) as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_file_path = temp_file.name

            print(f"Processing file: {file.filename}")

            # --- THIS IS WHERE WE CALL YOUR SCRIPT ---
            parsed_data = extract_single_resume(temp_file_path)
            # ------------------------------------------

            if parsed_data:
                # Prepare data for Supabase table
                data_to_insert = {
                    "file_name": file.filename,
                    "personal_info": parsed_data.get("personal_info"),
                    "skills": parsed_data.get("skills"),
                    "education": parsed_data.get("education"),
                    "experience": parsed_data.get("experience"),
                    "projects": parsed_data.get("projects"),
                    "certifications": parsed_data.get("certifications"),
                    "achievements": parsed_data.get("achievements"),
                }

                # Insert into Supabase
                response = supabase.table("resumes").insert(data_to_insert).execute()

                if response.data:
                    print(f"Successfully saved to Supabase: {file.filename}")
                    success_files.append(file.filename)
                else:
                    print(f"Error saving to Supabase: {response.error.message}")
                    errors.append({"file": file.filename, "error": str(response.error.message)})

            else:
                errors.append({"file": file.filename, "error": "Parser returned no data."})

        except Exception as e:
            print(f"Failed to process file {file.filename}: {e}")
            errors.append({"file": file.filename, "error": str(e)})

        finally:
            # Clean up the temporary file
            if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    return {
        "message": f"Processing complete. {len(success_files)} successful, {len(errors)} errors.",
        "successful_files": success_files,
        "errors": errors
    }

@app.get("/get-resumes/")
async def get_resumes():
    """
    Fetches all parsed resume data from Supabase.
    """
    try:
        response = supabase.table("resumes").select("*").order("created_at", desc=True).execute()
        if response.data:
            return response.data
        else:
            return {"data": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))