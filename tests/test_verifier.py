"""
Tests for verifier service: variation generation, scoring, entity verification.
DuckDuckGo search is mocked via unittest.mock.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.verifier import (
    generate_variations,
    score_result,
    verify_entity,
    verify_profile,
    compute_score,
    extract_entities,
    _compute_domain_similarity,
    _company_variations,
    _education_variations,
    _generate_abbreviation,
    _clean_company_name,
    _clean_education_name,
)
from app.services.search import search_web, _optimize_query, _search_sync


# ============================================================================
# Variation generation tests
# ============================================================================
class TestGenerateVariations:
    def test_education_variations(self):
        variations = generate_variations("Indian Institute of Technology Delhi", "education")
        assert "Indian Institute of Technology Delhi" in variations
        # Should generate IIT variation
        assert any("IIT" in v for v in variations)

    def test_education_university_removal(self):
        variations = generate_variations("Stanford University", "university")
        assert any("Stanford" == v.strip() for v in variations)

    def test_education_abbreviation(self):
        variations = generate_variations("Massachusetts Institute of Technology", "education")
        assert any(v.upper() == v and len(v) <= 5 for v in variations)

    def test_company_variations(self):
        variations = generate_variations("Google Technologies Inc", "experience")
        assert "Google Technologies Inc" in variations
        # Should remove suffix
        assert any("Inc" not in v for v in variations if v != "Google Technologies Inc")

    def test_company_abbreviation(self):
        variations = generate_variations("Advanced Micro Devices", "company")
        assert any(len(v) <= 5 and v == v.upper() for v in variations)

    def test_no_duplicates(self):
        variations = generate_variations("Google", "company")
        assert len(variations) == len(set(v.lower() for v in variations))


class TestCleanNames:
    def test_clean_company_name(self):
        assert _clean_company_name("Google Inc.") == "Google"
        assert _clean_company_name("Meta Platforms · Social Media") == "Meta Platforms"
        assert _clean_company_name("Amazon (E-commerce)") == "Amazon"

    def test_clean_education_name(self):
        assert _clean_education_name("MIT (Cambridge)") == "MIT"
        assert _clean_education_name("Stanford - California") == "Stanford"
        assert _clean_education_name("IIT Delhi, New Delhi") == "IIT Delhi"


class TestGenerateAbbreviation:
    def test_basic(self):
        assert _generate_abbreviation("Indian Institute Technology") == "iit"

    def test_stop_words_excluded(self):
        # "of" and "the" are stop words
        result = _generate_abbreviation("The Institute of Technology")
        assert "o" not in result  # "of" excluded
        assert "t" not in result or len(result) <= 2

    def test_empty(self):
        assert _generate_abbreviation("") == ""


# ============================================================================
# Scoring tests
# ============================================================================
class TestScoreResult:
    def test_education_with_edu_domain(self):
        result = {
            "href": "https://iitd.ac.in/about",
            "title": "IIT Delhi - Indian Institute of Technology Delhi",
            "body": "Premier engineering institution in India",
        }
        score = score_result(result, "IIT Delhi", "education")
        assert score["confidence"] > 0
        assert "domain" in score

    def test_education_strong_match(self):
        result = {
            "href": "https://stanford.edu",
            "title": "Stanford University Official Website",
            "body": "Stanford University is a private research university",
        }
        score = score_result(result, "Stanford University", "education")
        assert score["confidence"] >= 60

    def test_company_match(self):
        result = {
            "href": "https://google.com",
            "title": "Google - Official Website",
            "body": "Google LLC is a technology company",
        }
        score = score_result(result, "Google", "experience")
        assert score["confidence"] >= 60

    def test_company_with_official_indicator(self):
        result = {
            "href": "https://example.com/careers",
            "title": "Example Corp - Official Careers Page",
            "body": "Join our team at Example Corp",
        }
        score = score_result(result, "Example Corp", "experience")
        # Should get bonus for "official" and "careers"
        assert score["confidence"] > 0

    def test_no_match(self):
        result = {
            "href": "https://random-site.com",
            "title": "Cooking Recipes Blog",
            "body": "Best pasta recipes for beginners",
        }
        score = score_result(result, "Google", "experience")
        assert score["confidence"] < 60

    def test_confidence_capped_at_100(self):
        result = {
            "href": "https://google.com",
            "title": "Google Google Google Google",
            "body": "Google is Google official google",
        }
        score = score_result(result, "Google", "experience")
        assert score["confidence"] <= 100


class TestComputeDomainSimilarity:
    def test_direct_match(self):
        assert _compute_domain_similarity("google", "google") == 100.0

    def test_name_in_domain(self):
        assert _compute_domain_similarity("google", "google") == 100.0

    def test_abbreviation_match(self):
        # "iit" is abbreviation for "indian institute technology"
        result = _compute_domain_similarity("indian institute technology", "iit")
        assert result >= 85.0

    def test_no_match(self):
        result = _compute_domain_similarity("google", "facebook")
        assert result < 80.0


# ============================================================================
# Entity verification tests (mocked web search)
# ============================================================================
class TestVerifyEntity:
    @patch("app.services.verifier.search_web", new_callable=AsyncMock)
    async def test_verified_entity(self, mock_search, sample_search_results):
        mock_search.return_value = sample_search_results

        result = await verify_entity("IIT Delhi", "education")
        assert result["verified"] is True
        assert result["confidence"] >= 60

    @patch("app.services.verifier.search_web", new_callable=AsyncMock)
    async def test_unverified_entity(self, mock_search):
        mock_search.return_value = [
            {
                "href": "https://random.com",
                "title": "Random Blog",
                "body": "Nothing related",
            }
        ]
        result = await verify_entity("Fake University XYZ", "education")
        assert result["confidence"] < 60

    @patch("app.services.verifier.search_web", new_callable=AsyncMock)
    async def test_no_search_results(self, mock_search):
        mock_search.return_value = []
        result = await verify_entity("Nonexistent Corp", "company")
        assert result["verified"] is False
        assert result["confidence"] == 0
        assert result["match_type"] == "not_found"

    @patch("app.services.verifier.search_web", new_callable=AsyncMock)
    async def test_company_verification(self, mock_search):
        mock_search.return_value = [
            {
                "href": "https://google.com",
                "title": "Google - About",
                "body": "Google LLC is a technology company",
            }
        ]
        result = await verify_entity("Google", "company")
        assert result["verified"] is True


# ============================================================================
# Profile verification tests
# ============================================================================
class TestVerifyProfile:
    @patch("app.services.verifier.search_web", new_callable=AsyncMock)
    async def test_full_profile(self, mock_search):
        mock_search.return_value = [
            {
                "href": "https://iitd.ac.in",
                "title": "IIT Delhi",
                "body": "Indian Institute of Technology Delhi",
            }
        ]
        profile = {
            "publicIdentifier": "janedoe",
            "educations": [{"title": "IIT Delhi"}],
            "experiences": [{"subtitle": "Google", "title": "SWE"}],
        }
        result = await verify_profile(profile)
        assert "education" in result
        assert "experience" in result
        assert result["profile_url"] == "janedoe"

    @patch("app.services.verifier.search_web", new_callable=AsyncMock)
    async def test_empty_profile(self, mock_search):
        mock_search.return_value = []
        profile = {"publicIdentifier": "empty", "educations": [], "experiences": []}
        result = await verify_profile(profile)
        assert result["education"]["average_score"] == 0
        assert result["experience"]["average_score"] == 0


class TestExtractEntities:
    def test_linkedin_format(self):
        profile = {
            "educations": [{"title": "MIT"}],
            "experiences": [{"subtitle": "Google", "title": "SDE"}],
        }
        result = extract_entities(profile)
        assert len(result["educations"]) == 1
        assert result["educations"][0]["college"] == "MIT"
        assert len(result["experiences"]) == 1
        assert result["experiences"][0]["company"] == "Google"

    def test_empty_profile(self):
        result = extract_entities({})
        assert result["educations"] == []
        assert result["experiences"] == []

    def test_alternative_field_names(self):
        profile = {
            "educations": [{"schoolName": "Stanford"}],
            "experiences": [{"companyName": "Meta", "title": "Engineer"}],
        }
        result = extract_entities(profile)
        assert result["educations"][0]["college"] == "Stanford"
        assert result["experiences"][0]["company"] == "Meta"


class TestComputeScore:
    def test_all_verified(self):
        entries = [
            {"confidence": 90, "verified": True},
            {"confidence": 80, "verified": True},
        ]
        result = compute_score(entries, "education")
        assert result["average_score"] == 85.0
        assert result["overall_tag"] == "Verified"

    def test_mixed_results(self):
        entries = [
            {"confidence": 90, "verified": True},
            {"confidence": 30, "verified": False},
        ]
        result = compute_score(entries, "education")
        assert result["average_score"] == 60.0

    def test_empty_entries(self):
        result = compute_score([], "education")
        assert result["average_score"] == 0
        assert result["overall_tag"] == "Not Found"

    def test_tag_uncertain(self):
        entries = [{"confidence": 45, "verified": False}]
        result = compute_score(entries, "education")
        assert result["overall_tag"] == "Uncertain"

    def test_tag_likely_match(self):
        entries = [{"confidence": 65, "verified": True}]
        result = compute_score(entries, "education")
        assert result["overall_tag"] == "Likely Match"


# ============================================================================
# Search service tests (mocked DuckDuckGo)
# ============================================================================
class TestSearchService:
    def test_optimize_query_education(self):
        result = _optimize_query("IIT Delhi", "education")
        assert "university" in result
        assert "IIT Delhi" in result

    def test_optimize_query_university(self):
        result = _optimize_query("MIT", "university")
        assert "university" in result

    def test_optimize_query_company(self):
        result = _optimize_query("Google · Technology", "company")
        assert "official website" in result
        assert "·" not in result  # Cleaned

    def test_optimize_query_default(self):
        result = _optimize_query("random query", None)
        assert result == "random query"

    @patch("app.services.search.DDGS")
    def test_search_sync_success(self, mock_ddgs):
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.text.return_value = [
            {"href": "https://google.com", "title": "Google", "body": "Search engine"}
        ]
        mock_ddgs.return_value = mock_instance

        result = _search_sync("Google", "company")
        assert len(result) == 1

    @patch("app.services.search.DDGS")
    def test_search_sync_no_results(self, mock_ddgs):
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.text.return_value = []
        mock_ddgs.return_value = mock_instance

        result = _search_sync("NonexistentXYZ123", None)
        assert result == []

    @patch("app.services.search.DDGS")
    def test_search_sync_exception(self, mock_ddgs):
        mock_ddgs.side_effect = Exception("Network error")
        result = _search_sync("test", None)
        assert result == []

    @patch("app.services.search._search_sync")
    async def test_search_web_async(self, mock_sync):
        mock_sync.return_value = [{"href": "https://example.com"}]
        result = await search_web("test query", "education")
        assert len(result) == 1
