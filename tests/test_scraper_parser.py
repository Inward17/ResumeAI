"""
Tests for scraper (Apify) and parser (Gemini/langextract) services.
All external API calls fully mocked.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# ============================================================================
# Scraper tests (Apify)
# ============================================================================
class TestScraper:
    @patch("app.services.linkedinScraper.client")
    async def test_scrape_linkedin_success(self, mock_client):
        """Successful LinkedIn scraping returns profile data."""
        mock_dataset = MagicMock()
        mock_dataset.iterate_items.return_value = [
            {
                "firstName": "Jane",
                "lastName": "Doe",
                "headline": "Software Engineer",
                "positions": [{"title": "SWE", "companyName": "Google"}],
            }
        ]
        mock_run = {"defaultDatasetId": "test-dataset-id"}
        mock_actor = MagicMock()
        mock_actor.call.return_value = mock_run
        mock_client.actor.return_value = mock_actor
        mock_client.dataset.return_value = mock_dataset

        from app.services.linkedinScraper import scrape_linkedin_profiles

        result = await scrape_linkedin_profiles(["https://linkedin.com/in/janedoe"])
        assert result["status"] == "success"
        assert len(result["data"]) == 1
        assert result["data"][0]["firstName"] == "Jane"

    @patch("app.services.linkedinScraper.client", None)
    async def test_scrape_no_client_configured(self):
        """Should raise when APIFY_TOKEN is not set."""
        from app.services.linkedinScraper import scrape_linkedin_profiles

        with pytest.raises(Exception, match="not configured"):
            await scrape_linkedin_profiles(["https://linkedin.com/in/test"])

    @patch("app.services.linkedinScraper.client")
    async def test_scrape_api_error(self, mock_client):
        """Should propagate scraping errors."""
        mock_actor = MagicMock()
        mock_actor.call.side_effect = Exception("Apify rate limit exceeded")
        mock_client.actor.return_value = mock_actor

        from app.services.linkedinScraper import scrape_linkedin_profiles

        with pytest.raises(Exception, match="Scraping failed"):
            await scrape_linkedin_profiles(["https://linkedin.com/in/test"])

    @patch("app.services.linkedinScraper.client")
    async def test_scrape_multiple_profiles(self, mock_client):
        """Multiple profiles are passed as separate URLs."""
        profiles = [
            {"firstName": "Jane", "lastName": "Doe"},
            {"firstName": "John", "lastName": "Smith"},
        ]
        mock_dataset = MagicMock()
        mock_dataset.iterate_items.return_value = profiles
        mock_run = {"defaultDatasetId": "ds-id"}
        mock_actor = MagicMock()
        mock_actor.call.return_value = mock_run
        mock_client.actor.return_value = mock_actor
        mock_client.dataset.return_value = mock_dataset

        from app.services.linkedinScraper import scrape_linkedin_profiles

        result = await scrape_linkedin_profiles([
            "https://linkedin.com/in/janedoe",
            "https://linkedin.com/in/johnsmith",
        ])
        assert result["status"] == "success"
        assert len(result["data"]) == 2


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
