"""
Tests for utility modules: date_utils, text_utils, file_utils
Pure-function tests — no external API mocking needed.
"""
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import io

# ============================================================================
# date_utils tests
# ============================================================================
from app.utils.date_utils import (
    parse_github_date,
    analyze_commit_spread,
    get_most_recent_commit_date,
    calculate_commit_consistency,
)


class TestParseGithubDate:
    def test_valid_date(self):
        result = parse_github_date("2024-01-15T10:30:00Z")
        assert result == datetime(2024, 1, 15, 10, 30, 0)

    def test_midnight(self):
        result = parse_github_date("2024-12-31T00:00:00Z")
        assert result == datetime(2024, 12, 31, 0, 0, 0)

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            parse_github_date("not-a-date")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_github_date("")


class TestAnalyzeCommitSpread:
    def test_empty_dates(self):
        result = analyze_commit_spread([])
        assert result["total_commits"] == 0
        assert result["unique_days"] == 0
        assert result["is_dump_pattern"] is False

    def test_single_day(self):
        dates = ["2024-01-15T10:30:00Z", "2024-01-15T14:00:00Z"]
        result = analyze_commit_spread(dates)
        assert result["total_commits"] == 2
        assert result["unique_days"] == 1
        assert result["is_dump_pattern"] is True  # 100% on one day

    def test_spread_across_days(self):
        dates = [
            "2024-01-15T10:30:00Z",
            "2024-02-10T12:00:00Z",
            "2024-03-05T09:15:00Z",
            "2024-04-20T16:45:00Z",
            "2024-05-10T11:30:00Z",
        ]
        result = analyze_commit_spread(dates)
        assert result["total_commits"] == 5
        assert result["unique_days"] == 5
        assert result["is_dump_pattern"] is False

    def test_dump_pattern_detected(self):
        # 7 of 10 commits on same day → 70%
        dates = ["2024-01-15T10:00:00Z"] * 7 + [
            "2024-02-10T12:00:00Z",
            "2024-03-05T09:00:00Z",
            "2024-04-20T16:00:00Z",
        ]
        result = analyze_commit_spread(dates)
        assert result["is_dump_pattern"] is True
        assert result["max_day_ratio"] >= 0.70

    def test_invalid_dates_ignored(self):
        dates = ["not-a-date", "also-bad"]
        result = analyze_commit_spread(dates)
        assert result["total_commits"] == 0

    def test_date_range_days(self):
        dates = ["2024-01-01T00:00:00Z", "2024-01-31T00:00:00Z"]
        result = analyze_commit_spread(dates)
        assert result["date_range_days"] == 30


class TestGetMostRecentCommitDate:
    def test_multiple_dates(self):
        dates = [
            "2024-01-15T10:30:00Z",
            "2024-06-01T14:00:00Z",
            "2024-03-05T09:15:00Z",
        ]
        result = get_most_recent_commit_date(dates)
        assert "2024-06-01" in result

    def test_empty_list(self):
        assert get_most_recent_commit_date([]) == ""

    def test_single_date(self):
        result = get_most_recent_commit_date(["2024-05-10T11:30:00Z"])
        assert "2024-05-10" in result


class TestCalculateCommitConsistency:
    def test_few_commits(self):
        assert calculate_commit_consistency(["2024-01-15T10:30:00Z"]) == 0.0

    def test_perfect_consistency(self):
        dates = ["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z", "2024-01-03T00:00:00Z"]
        result = calculate_commit_consistency(dates)
        assert result == 1.0  # 3 commits on 3 unique days

    def test_low_consistency(self):
        # 5 commits on same day
        dates = ["2024-01-01T00:00:00Z"] * 5
        result = calculate_commit_consistency(dates)
        assert result == 0.2  # 1 unique day / 5 commits


# ============================================================================
# text_utils tests
# ============================================================================
from app.utils.text_utils import (
    extract_keywords_from_text,
    clean_text,
    is_trivial_repo_name,
    calculate_text_similarity,
)


class TestExtractKeywordsFromText:
    def test_python_detected(self):
        result = extract_keywords_from_text("This project uses Python and Django")
        assert "Python" in result

    def test_javascript_detected(self):
        result = extract_keywords_from_text("Built with React and Node.js")
        assert "JavaScript" in result

    def test_multiple_languages(self):
        result = extract_keywords_from_text("Uses Python, React, and Java with Spring Boot")
        assert "Python" in result
        assert "JavaScript" in result
        assert "Java" in result

    def test_empty_text(self):
        assert extract_keywords_from_text("") == set()
        assert extract_keywords_from_text(None) == set()

    def test_no_matches(self):
        result = extract_keywords_from_text("This is about cooking recipes")
        assert len(result) == 0

    def test_case_insensitive(self):
        result = extract_keywords_from_text("PYTHON and REACT")
        assert "Python" in result
        assert "JavaScript" in result


class TestCleanText:
    def test_excessive_whitespace(self):
        result = clean_text("hello    world   test")
        assert result == "hello world test"

    def test_code_blocks_removed(self):
        result = clean_text("before ```python\ncode here\n``` after")
        assert "code here" not in result
        assert "before" in result
        assert "after" in result

    def test_empty_text(self):
        assert clean_text("") == ""
        assert clean_text(None) == ""


class TestIsTrivialRepoName:
    def test_trivial_names(self):
        from app.utils.constants import TRIVIAL_REPO_PATTERNS
        assert is_trivial_repo_name("todo-app", TRIVIAL_REPO_PATTERNS) is True
        assert is_trivial_repo_name("react-clone", TRIVIAL_REPO_PATTERNS) is True
        assert is_trivial_repo_name("calculator-v2", TRIVIAL_REPO_PATTERNS) is True
        assert is_trivial_repo_name("my-test-project", TRIVIAL_REPO_PATTERNS) is True

    def test_non_trivial_names(self):
        from app.utils.constants import TRIVIAL_REPO_PATTERNS
        assert is_trivial_repo_name("kubernetes-operator", TRIVIAL_REPO_PATTERNS) is False
        assert is_trivial_repo_name("resume-parser", TRIVIAL_REPO_PATTERNS) is False


class TestCalculateTextSimilarity:
    def test_identical_texts(self):
        result = calculate_text_similarity("hello world", "hello world")
        assert result == 1.0

    def test_no_overlap(self):
        result = calculate_text_similarity("hello world", "foo bar")
        assert result == 0.0

    def test_partial_overlap(self):
        result = calculate_text_similarity("hello world foo", "hello bar baz")
        assert 0.0 < result < 1.0

    def test_empty_text(self):
        assert calculate_text_similarity("", "hello") == 0.0
        assert calculate_text_similarity("hello", "") == 0.0
        assert calculate_text_similarity(None, None) == 0.0


# ============================================================================
# file_utils tests
# ============================================================================
from app.utils.file_utils import read_file, read_pdf_bytes, read_docx_bytes


class TestReadFile:
    def test_txt_file(self):
        content = b"Hello, this is a text resume."
        result = read_file("resume.txt", content)
        assert result == "Hello, this is a text resume."

    @patch("app.utils.file_utils.pdfplumber")
    def test_pdf_file(self, mock_pdfplumber):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "PDF resume content"
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        mock_pdfplumber.open.return_value = mock_pdf
        result = read_file("resume.pdf", b"fake-pdf-bytes")
        assert result == "PDF resume content"

    @patch("app.utils.file_utils.docx")
    def test_docx_file(self, mock_docx):
        mock_para1 = MagicMock()
        mock_para1.text = "Line 1"
        mock_para2 = MagicMock()
        mock_para2.text = "Line 2"
        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para1, mock_para2]
        mock_docx.Document.return_value = mock_doc
        result = read_file("resume.docx", b"fake-docx-bytes")
        assert "Line 1" in result
        assert "Line 2" in result

    def test_txt_with_unicode(self):
        content = "Résumé with spëcial chars".encode("utf-8")
        result = read_file("resume.txt", content)
        assert "Résumé" in result
