import asyncio
import os
import sys

# Ensure backend directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.github_services_v2 import verify_github

async def main():
    print("Starting GitHub Analysis Pipeline for profiling...")
    
    # Setup a sample candidate request
    # 'tiangolo' is a good heavy profile to test rate limits and processing
    parsed_resume = {
        "github_username": "sohamminiyar",
        "personal_info": {"github": "github.com/sohamminiyar"}
    }
    
    # We use explicit candidate_id to simulate the real workflow
    result = await verify_github(
        candidate_id="sohamminiyar", 
        parsed_resume=parsed_resume
    )
    
    print(f"Analysis Complete!")
    print(f"Success: {result.success}")
    if result.success:
         print(f"Score: {result.score100}")
    else:
         print(f"Error: {result.error}")

if __name__ == "__main__":
    asyncio.run(main())
