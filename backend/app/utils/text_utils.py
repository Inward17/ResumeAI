"""
Text utilities for README and keyword analysis
"""
import re
from typing import List, Set
from .constants import LANGUAGE_KEYWORDS


def extract_keywords_from_text(text: str) -> Set[str]:
    """
    Extract programming language keywords from text (case-insensitive)
    
    Args:
        text: Input text (usually README content)
        
    Returns:
        Set of detected language names
    """
    if not text:
        return set()
    
    text_lower = text.lower()
    detected_languages = set()
    
    for language, keywords in LANGUAGE_KEYWORDS.items():
        for keyword in keywords:
            # Use word boundaries to avoid false positives
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            if re.search(pattern, text_lower):
                detected_languages.add(language)
                break  # Found this language, no need to check other keywords
    
    return detected_languages


def clean_text(text: str) -> str:
    """
    Clean and normalize text
    
    Args:
        text: Input text
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove markdown code blocks for cleaner analysis
    text = re.sub(r'```[\s\S]*?```', '', text)
    
    return text.strip()


def is_trivial_repo_name(repo_name: str, trivial_patterns: List[str]) -> bool:
    """
    Check if repository name matches trivial patterns
    
    Args:
        repo_name: Repository name
        trivial_patterns: List of trivial patterns
        
    Returns:
        True if repo name is considered trivial
    """
    repo_name_lower = repo_name.lower()
    
    for pattern in trivial_patterns:
        if pattern in repo_name_lower:
            return True
    
    return False


def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    Simple word-overlap similarity between two texts
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        Similarity score (0.0 to 1.0)
    """
    if not text1 or not text2:
        return 0.0
    
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union) if union else 0.0