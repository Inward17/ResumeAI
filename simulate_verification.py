"""
Live simulation of the Enterprise GitHub Verification Engine
Test Case 1: octocat -- GitHub link only, NO resume projects
Test Case 2: POPPz07 -- 3 resume projects, full pipeline
"""

import asyncio
import json
import sys
import os
import time
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env from project root BEFORE importing services
# so config.py picks up GITHUB_TOKEN via os.getenv()
from dotenv import load_dotenv
load_dotenv()

# Only show our service logs at WARNING+ to suppress httpx/model noise
logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(name)s | %(message)s")
# But keep our service at INFO
logging.getLogger("services.github_services").setLevel(logging.INFO)

from services.github_services import verify_github


def pretty(obj) -> str:
    """Convert dataclass result to pretty JSON."""
    if hasattr(obj, "to_mongo_dict"):
        return json.dumps(obj.to_mongo_dict(), indent=2, default=str)
    if hasattr(obj, "__dataclass_fields__"):
        import dataclasses
        return json.dumps(dataclasses.asdict(obj), indent=2, default=str)
    return str(obj)


async def main():
    overall_start = time.perf_counter()

    # ===========================================================
    # TEST CASE 1 -- octocat: GitHub username only, NO projects
    # ===========================================================
    print("=" * 70)
    print("TEST CASE 1: octocat -- No projects in resume")
    print("=" * 70)
    print()

    resume_octocat = {
        "github_username": "octocat",
        "projects": [],
    }

    t1_start = time.perf_counter()
    result1 = await verify_github(candidate_id="SIM-001", parsed_resume=resume_octocat)
    t1_elapsed = time.perf_counter() - t1_start
    print(f"[TIMING] TC1 elapsed: {t1_elapsed:.2f}s")
    print()

    print(f"Success:          {result1.success}")
    print(f"Username:         {result1.username}")
    print(f"Score (0-100):    {result1.score100}")
    print(f"Score (0-40):     {result1.score40}")
    print(f"Confidence:       {result1.confidenceLevel}")
    print(f"Red Flags:        {result1.redFlags}")
    if result1.repositoryStats:
        rs = result1.repositoryStats
        print(f"Repos Total:      {rs.total}")
        print(f"  Original:       {rs.original}")
        print(f"  Forked:         {rs.forked}")
        print(f"  Trivial:        {rs.trivial}")
        print(f"  RepoAuth:       {rs.repositoryAuthenticity}")
    if result1.resumeVerification:
        rv = result1.resumeVerification
        print(f"Resume Claimed:   {rv.projectsClaimed}")
        print(f"  Matched:        {rv.projectsMatched}")
        print(f"  Not Found:      {rv.projectsNotFound}")
        print(f"  Consistency:    {rv.resumeConsistency}")
    if result1.signals:
        print(f"Signals:          RC={result1.signals.ResumeConsistency}, "
              f"RA={result1.signals.RepositoryAuthenticity}, "
              f"RO={result1.signals.ReadmeOriginality}, "
              f"CO={result1.signals.CodeOriginality}, "
              f"BA={result1.signals.BehavioralAuthenticity}, "
              f"OSS={result1.signals.OSSContribution}")
    print()
    print("--- Mongo Document ---")
    print(pretty(result1))

    # ===========================================================
    # TEST CASE 2 -- POPPz07: 3 resume projects
    # ===========================================================
    print()
    print("=" * 70)
    print("TEST CASE 2: POPPz07 -- 3 resume projects")
    print("=" * 70)
    print()

    resume_poppz07 = {
        "github_username": "POPPz07",
        "projects": [
            {
                "name": "Code Vulnerability Detection System",
                "description": "Static code analysis tool using local open-source LLMs to detect insecure or low-quality code patterns. AST-based preprocessing pipeline.",
            },
            {
                "name": "E-commerce Aggregator Web App",
                "description": "ETL workflows to aggregate preprocess and store product pricing data. Scraping logic with REST APIs and basic authentication.",
            },
            {
                "name": "Hybrid Movie Recommendation System",
                "description": "Full-stack recommendation system combining content-based and collaborative filtering. Backend APIs, MongoDB Atlas, React frontend.",
            },
        ],
    }

    t2_start = time.perf_counter()
    result2 = await verify_github(candidate_id="SIM-002", parsed_resume=resume_poppz07)
    t2_elapsed = time.perf_counter() - t2_start
    print(f"[TIMING] TC2 elapsed: {t2_elapsed:.2f}s")
    print()

    print(f"Success:          {result2.success}")
    print(f"Username:         {result2.username}")
    print(f"Score (0-100):    {result2.score100}")
    print(f"Score (0-40):     {result2.score40}")
    print(f"Confidence:       {result2.confidenceLevel}")
    print(f"Red Flags:        {result2.redFlags}")
    if result2.repositoryStats:
        rs = result2.repositoryStats
        print(f"Repos Total:      {rs.total}")
        print(f"  Original:       {rs.original}")
        print(f"  Forked:         {rs.forked}")
        print(f"  Trivial:        {rs.trivial}")
        print(f"  RepoAuth:       {rs.repositoryAuthenticity}")
    if result2.resumeVerification:
        rv = result2.resumeVerification
        print(f"Resume Claimed:   {rv.projectsClaimed}")
        print(f"  Matched:        {rv.projectsMatched}")
        print(f"  Not Found:      {rv.projectsNotFound}")
        print(f"  Consistency:    {rv.resumeConsistency}")
        for m in rv.matches:
            print(f"    - {m.projectName} <-> {m.repoName} "
                  f"(sim={m.similarity}, stage={m.matchStage}, strength={m.matchStrength})")
    if result2.cloneAnalysis:
        ca = result2.cloneAnalysis
        print(f"Clone Analysis:")
        print(f"  README sim max: {ca.readmeSimilarityMax} ({ca.readmeVerdict})")
        print(f"  Code sim max:   {ca.codeSimilarityMax} ({ca.codeVerdict})")
        print(f"  README orig:    {ca.readmeOriginality}")
        print(f"  Code orig:      {ca.codeOriginality}")
    if result2.behavioralAnalysis:
        ba = result2.behavioralAnalysis
        print(f"Behavioral:")
        print(f"  Consistency:    {ba.commitConsistency}")
        print(f"  Burst Risk:     {ba.burstRisk}")
        print(f"  Msg Quality:    {ba.messageQuality}")
        print(f"  File Diversity: {ba.fileDiversity}")
        print(f"  Auth Score:     {ba.behavioralAuthenticity}")
        print(f"  OSS Score:      {ba.ossContributionScore}")
    if result2.signals:
        print(f"Signals:          RC={result2.signals.ResumeConsistency}, "
              f"RA={result2.signals.RepositoryAuthenticity}, "
              f"RO={result2.signals.ReadmeOriginality}, "
              f"CO={result2.signals.CodeOriginality}, "
              f"BA={result2.signals.BehavioralAuthenticity}, "
              f"OSS={result2.signals.OSSContribution}")
    if result2.llmEscalation:
        print(f"LLM Escalation:   {result2.llmEscalation}")
    print()
    print("--- Mongo Document ---")
    print(pretty(result2))

    print()
    overall_elapsed = time.perf_counter() - overall_start
    print("=" * 70)
    print(f"SIMULATION COMPLETE  (total: {overall_elapsed:.2f}s)")
    print(f"  TC1 octocat: {t1_elapsed:.2f}s")
    print(f"  TC2 POPPz07: {t2_elapsed:.2f}s")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
