"""
Tests for the LinkedIn lookup (Firecrawl, Apify fallback) and parser (Gemini/langextract) services.
All external API calls fully mocked.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

SCRAPER = "app.services.linkedinScraper"


def _apify(items=None, error=None):
    """Mock ApifyClient whose actor run yields ``items`` (or raises ``error``)."""
    client = MagicMock()
    actor = MagicMock()
    if error:
        actor.call.side_effect = error
    else:
        actor.call.return_value = {"defaultDatasetId": "ds-id"}
        client.dataset.return_value.iterate_items.return_value = items or []
    client.actor.return_value = actor
    return client


# ============================================================================
# LinkedIn lookup tests (Firecrawl first, Apify fallback)
# ============================================================================
class TestScraper:
    async def test_apify_used_when_firecrawl_not_configured(self):
        client = _apify([{"firstName": "Jane", "positions": [{"title": "SWE", "companyName": "Google"}]}])
        with patch(f"{SCRAPER}.FIRECRAWL_API_KEY", None), patch(f"{SCRAPER}._apify", client):
            from app.services.linkedinScraper import scrape_linkedin_profiles
            result = await scrape_linkedin_profiles(["https://linkedin.com/in/janedoe"])
        assert result["status"] == "success"
        assert result["data"][0]["firstName"] == "Jane"

    async def test_raises_when_nothing_configured(self):
        with patch(f"{SCRAPER}.FIRECRAWL_API_KEY", None), patch(f"{SCRAPER}._apify", None):
            from app.services.linkedinScraper import scrape_linkedin_profiles
            with pytest.raises(Exception, match="not configured"):
                await scrape_linkedin_profiles(["https://linkedin.com/in/test"])

    async def test_apify_error_propagates_when_it_is_the_only_source(self):
        with patch(f"{SCRAPER}.FIRECRAWL_API_KEY", None), \
                patch(f"{SCRAPER}._apify", _apify(error=Exception("Apify rate limit exceeded"))):
            from app.services.linkedinScraper import scrape_linkedin_profiles
            with pytest.raises(Exception, match="Scraping failed"):
                await scrape_linkedin_profiles(["https://linkedin.com/in/test"])

    async def test_firecrawl_result_skips_apify(self):
        client = _apify([{"firstName": "Should not be used"}])
        lookup = AsyncMock(return_value={"firstName": "Jane", "source": "firecrawl"})
        with patch(f"{SCRAPER}.FIRECRAWL_API_KEY", "fc-test"), patch(f"{SCRAPER}._apify", client), \
                patch(f"{SCRAPER}._firecrawl_lookup", lookup):
            from app.services.linkedinScraper import scrape_linkedin_profiles
            result = await scrape_linkedin_profiles(["https://linkedin.com/in/janedoe"])
        assert [p["firstName"] for p in result["data"]] == ["Jane"]
        client.actor.assert_not_called()

    async def test_profiles_firecrawl_misses_fall_back_to_apify(self):
        client = _apify([{"firstName": "John"}])
        # First profile found by Firecrawl, second not found, third errors
        lookup = AsyncMock(side_effect=[{"firstName": "Jane"}, None, Exception("HTTP 500")])
        urls = ["https://linkedin.com/in/jane", "https://linkedin.com/in/john", "https://linkedin.com/in/err"]
        with patch(f"{SCRAPER}.FIRECRAWL_API_KEY", "fc-test"), patch(f"{SCRAPER}._apify", client), \
                patch(f"{SCRAPER}._firecrawl_lookup", lookup):
            from app.services.linkedinScraper import scrape_linkedin_profiles
            result = await scrape_linkedin_profiles(urls)
        assert [p["firstName"] for p in result["data"]] == ["Jane", "John"]
        run_input = client.actor.return_value.call.call_args.kwargs["run_input"]
        assert [u["url"] for u in run_input["urls"]] == urls[1:]

    def test_firecrawl_profile_mapped_to_verifier_shape(self):
        from app.services.linkedinScraper import _to_apify_shape, _canonical
        person = {
            "id": "p1", "first_name": "Jane", "last_name": "Doe", "headline": "Engineer",
            "location": {"city": "Pune", "country": "India", "country_code": "IN"},
            "employment": {"all": [{"title": "SWE", "company": {"name": "Acme"}, "start_at": "2021-03-01T00:00:00Z"}]},
            "educations": [{"school_name": "VIT", "end_at": "2020-06-01T00:00:00Z"}],
            "skills": ["Python", {"bad": 1}],
            "social_profiles": {"professional_network": {"url": "https://www.linkedin.com/in/janedoe", "handle": "janedoe"}},
        }
        out = _to_apify_shape(person, "https://linkedin.com/in/janedoe")
        assert out["positions"][0]["companyName"] == "Acme"
        assert out["positions"][0]["timePeriod"] == {"startDate": {"month": 3, "year": 2021}, "endDate": None}
        assert out["educations"][0]["schoolName"] == "VIT"
        assert out["location"] == "Pune, India" and out["skills"] == ["Python"]
        assert _canonical("linkedin.com/in/jane-doe/?trk=x") == "https://www.linkedin.com/in/jane-doe"


# ============================================================================
# Parser tests (Gemini/langextract mocked)
# ============================================================================
class TestParser:
    def _make_mock_extraction(self, cls, text):
        ext = MagicMock()
        ext.extraction_class = cls
        ext.extraction_text = text
        return ext

    @patch("app.services.parser.lx.extract")
    async def test_parse_full_resume(self, mock_extract):
        """Full resume extraction with all fields."""
        mock_result = MagicMock()
        mock_result.extractions = [
            self._make_mock_extraction("full_name", "Jane Doe"),
            self._make_mock_extraction("email", "jane@example.com"),
            self._make_mock_extraction("phone_number", "+1 555-987-6543"),
            self._make_mock_extraction("github", "github.com/janedoe"),
            self._make_mock_extraction("linkedin", "linkedin.com/in/janedoe"),
            self._make_mock_extraction("skills", "Python, FastAPI, React"),
            self._make_mock_extraction("education", "B.Tech CS, IIT Delhi, 2021"),
            self._make_mock_extraction("experience", "SWE at Google (2021-2024)"),
            self._make_mock_extraction("projects", "E-commerce Platform (Jan-Mar 2023) - Built full-stack app"),
            self._make_mock_extraction("university", "IIT Delhi"),
            self._make_mock_extraction("company", "Google"),
            self._make_mock_extraction("certifications", "AWS Certified"),
            self._make_mock_extraction("achievements", "Won Hackathon"),
        ]
        mock_extract.return_value = mock_result

        from app.services.parser import parse_resume

        result = await parse_resume("dummy resume text")

        assert result["personal_info"]["full_name"] == "Jane Doe"
        assert result["personal_info"]["email"] == "jane@example.com"
        assert result["personal_info"]["github"] == "github.com/janedoe"
        assert "Python" in result["skills"]
        assert len(result["education"]) == 1
        assert len(result["experience"]) == 1
        assert result["university"] == ["IIT Delhi"]
        assert result["company"] == ["Google"]

    @patch("app.services.parser.lx.extract")
    async def test_parse_minimal_resume(self, mock_extract):
        """Resume with only name and email."""
        mock_result = MagicMock()
        mock_result.extractions = [
            self._make_mock_extraction("full_name", "John Smith"),
            self._make_mock_extraction("email", "john@example.com"),
        ]
        mock_extract.return_value = mock_result

        from app.services.parser import parse_resume

        result = await parse_resume("John Smith john@example.com")

        assert result["personal_info"]["full_name"] == "John Smith"
        assert result["skills"] is None
        assert result["education"] is None

    @patch("app.services.parser.lx.extract")
    async def test_parse_projects(self, mock_extract):
        """Projects are parsed into structured format."""
        mock_result = MagicMock()
        mock_result.extractions = [
            self._make_mock_extraction(
                "projects",
                "E-commerce Platform (Jan-Mar 2023) - Built with Python, React - Payment integration"
            ),
            self._make_mock_extraction(
                "projects",
                "Task App (Apr 2023) - Built with React, Node.js - Real-time features"
            ),
        ]
        mock_extract.return_value = mock_result

        from app.services.parser import parse_resume

        result = await parse_resume("resume text")
        assert result["projects"] is not None
        assert len(result["projects"]) == 2
        assert result["projects"][0]["name"] != ""

    @patch("app.services.parser.lx.extract")
    async def test_parse_duplicate_skills_deduplicated(self, mock_extract):
        """Duplicate skill entries should be deduplicated."""
        mock_result = MagicMock()
        mock_result.extractions = [
            self._make_mock_extraction("skills", "Python, React"),
            self._make_mock_extraction("skills", "Python, React"),
        ]
        mock_extract.return_value = mock_result

        from app.services.parser import parse_resume

        result = await parse_resume("text")
        # The skill text is the same, so it should only appear once
        assert result["skills"].count("Python") == 1


# ============================================================================
# parse_projects standalone tests
# ============================================================================
class TestParseProjects:
    def _make_extraction(self, text):
        ext = MagicMock()
        ext.extraction_class = "projects"
        ext.extraction_text = text
        return ext

    def test_project_with_duration(self):
        from app.services.parser import parse_projects

        extractions = [
            self._make_extraction("Task Manager (Spring 2023) - Built with React, MongoDB - Real time features")
        ]
        result = parse_projects(extractions)
        assert len(result) == 1
        assert result[0]["duration"] == "Spring 2023"
        assert "Task Manager" in result[0]["name"]

    def test_project_with_technologies(self):
        from app.services.parser import parse_projects

        extractions = [
            self._make_extraction("My App - Built with Python, React, MongoDB")
        ]
        result = parse_projects(extractions)
        assert "Python" in result[0]["technologies"]
        assert "React" in result[0]["technologies"]
        assert "MongoDB" in result[0]["technologies"]

    def test_empty_extractions(self):
        from app.services.parser import parse_projects

        result = parse_projects([])
        assert result == []

    def test_non_project_extractions_filtered(self):
        from app.services.parser import parse_projects

        ext = MagicMock()
        ext.extraction_class = "skills"
        ext.extraction_text = "Python, React"
        result = parse_projects([ext])
        assert result == []
