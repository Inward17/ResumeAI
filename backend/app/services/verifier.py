"""
Verifier service - handles verification, scoring, and variation generation
"""
import re
import asyncio
from typing import List, Dict
from rapidfuzz import fuzz
import tldextract
from itertools import permutations

from app.services.search import search_web


# ============================================================================
# VARIATION GENERATION
# ============================================================================

def generate_variations(name: str, field_type: str) -> List[str]:
    """Generate all name variations for searching"""
    variations = [name]
    
    if field_type in ("education", "university"):
        variations.extend(_education_variations(name))
    else:  # experience or company
        variations.extend(_company_variations(name))
    
    # Remove duplicates
    seen = set()
    unique = []
    for v in variations:
        v_lower = v.lower().strip()
        if v_lower and v_lower not in seen:
            seen.add(v_lower)
            unique.append(v)
    
    return unique


def _company_variations(name: str) -> List[str]:
    """Generate company name variations"""
    variations = []
    clean = _clean_company_name(name)
    words = clean.split()
    
    # Remove suffixes
    no_suffix = re.sub(
        r'\s*(Inc|LLC|Ltd|Pvt|Corp|Technologies?|Solutions?|Services?|Works?)\s*$',
        '', clean, flags=re.IGNORECASE
    ).strip()
    if no_suffix != clean:
        variations.append(no_suffix)
    
    # Word reordering (2-3 words only)
    if 2 <= len(words) <= 3:
        for perm in permutations(words):
            variations.append(' '.join(perm))
    
    # Singular/plural swaps
    for idx, word in enumerate(words):
        if word.lower() in ['work', 'works']:
            modified = words.copy()
            modified[idx] = 'Works' if word.lower() == 'work' else 'Work'
            variations.append(' '.join(modified))
    
    # Abbreviation
    abbr = _generate_abbreviation(clean)
    if abbr and len(abbr) >= 2:
        variations.append(abbr.upper())
    
    return variations


def _education_variations(name: str) -> List[str]:
    """Generate university name variations"""
    variations = []
    clean = _clean_education_name(name)
    words = clean.split()
    
    # Remove location (last 1-2 words)
    if len(words) > 3:
        variations.append(' '.join(words[:-1]))
    
    # Add/remove "University"
    if 'university' in clean.lower():
        no_univ = re.sub(r'\s*university\s*', ' ', clean, flags=re.IGNORECASE).strip()
        variations.append(no_univ)
    else:
        variations.append(f"{clean} University")
    
    # Abbreviation
    abbr = _generate_abbreviation(clean)
    if abbr and len(abbr) >= 2:
        variations.append(abbr.upper())
    
    # IIT pattern
    if 'institute of technology' in clean.lower():
        variations.append(clean.replace('Institute of Technology', 'IIT'))
    
    return variations


def _generate_abbreviation(text: str) -> str:
    """Generate abbreviation from text"""
    stop_words = {'the', 'of', 'and', 'for', 'in', 'at', 'university', 'college', 'limited', 'private'}
    words = [w for w in text.lower().split() if w not in stop_words and len(w) > 2]
    return ''.join(word[0] for word in words) if words else ""


def _clean_company_name(name: str) -> str:
    """Clean company name"""
    name = re.sub(r'\s*(Inc\.|LLC|Ltd\.|Pvt\.|Corp\.)', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*·.*$', '', name)
    name = re.sub(r'\s*\(.*?\)', '', name)
    return name.strip()


def _clean_education_name(name: str) -> str:
    """Clean university name"""
    name = re.sub(r'\s*\(.*?\)', '', name)
    name = re.sub(r'\s*-\s*.*$', '', name)
    name = re.sub(r'\s*,.*$', '', name)
    return name.strip()


# ============================================================================
# SCORING & VERIFICATION
# ============================================================================

def score_result(result: dict, name: str, field_type: str) -> dict:
    """Score a single search result"""
    url = result.get('href', '')
    title = result.get('title', '').lower()
    snippet = result.get('body', '').lower()
    
    # Extract domain
    domain_info = tldextract.extract(url)
    domain = domain_info.domain
    suffix = domain_info.suffix
    
    confidence = 0
    match_type = "no_match"
    
    clean_name = (_clean_education_name(name) if field_type in ("education", "university")
                  else _clean_company_name(name)).lower()
    
    # Text similarity (title + snippet)
    text_sim = max(
        fuzz.token_set_ratio(clean_name, title),
        fuzz.token_sort_ratio(clean_name, title),
        fuzz.partial_ratio(clean_name, title),
        fuzz.token_set_ratio(clean_name, snippet)
    )
    
    # Domain similarity
    domain_sim = _compute_domain_similarity(clean_name, domain)
    
    # Scoring
    if field_type in ("education", "university"):
        # Educational TLD bonus
        if any(pattern in suffix for pattern in ['.edu', '.ac']):
            confidence += 20
            match_type = "domain_match"
        
        # Domain match
        if domain_sim >= 85:
            confidence += 35
            match_type = "strong_domain_match"
        elif domain_sim >= 70:
            confidence += 25
        
        # Text match
        if text_sim >= 85:
            confidence += 45
        elif text_sim >= 70:
            confidence += 30
        elif text_sim >= 60:
            confidence += 20
        
        # Strong title match overrides weak domain
        if text_sim >= 80:
            confidence = max(confidence, 75)
            
    else:  # experience
        # Domain match
        if domain_sim >= 85:
            confidence += 40
            match_type = "strong_domain_match"
        elif domain_sim >= 70:
            confidence += 30
        
        # Text match
        if text_sim >= 85:
            confidence += 45
        elif text_sim >= 70:
            confidence += 30
        elif text_sim >= 60:
            confidence += 20
        
        # Official indicators
        if any(word in title for word in ['official', 'careers', 'about']):
            confidence += 10
        
        # Strong title match overrides
        if text_sim >= 80:
            confidence = max(confidence, 75)
    
    confidence = min(confidence, 100)
    
    return {
        "confidence": round(confidence, 2),
        "match_type": match_type,
        "domain": f"{domain}.{suffix}",
        "title": result.get('title'),
        "snippet": result.get('body'),
        "url": url
    }


def _compute_domain_similarity(name: str, domain: str) -> float:
    """Compute similarity between name and domain"""
    name = name.lower().strip()
    domain = domain.lower().strip()
    
    # Direct match
    if name in domain or domain in name:
        return 100.0
    
    # Abbreviation match
    abbr = _generate_abbreviation(name)
    if abbr and abbr == domain:
        return 95.0
    if abbr and abbr in domain:
        return 85.0
    
    # Word matching
    name_words = [w for w in name.split() if len(w) > 2]
    if name_words:
        matches = sum(1 for word in name_words if word in domain)
        if matches > 0:
            ratio = matches / len(name_words)
            if ratio >= 0.7:
                return 80.0
            elif ratio >= 0.5:
                return 70.0
    
    # Fuzzy matching
    return max(
        fuzz.ratio(name, domain),
        fuzz.partial_ratio(name, domain),
        fuzz.token_set_ratio(name, domain)
    )


# ============================================================================
# MAIN VERIFICATION FUNCTIONS
# ============================================================================

async def verify_entity(name: str, field_type: str) -> dict:
    """
    Verify a single entity (company or university)
    
    Returns:
        dict with verified, confidence, top_result, etc.
    """
    # Generate variations
    variations = generate_variations(name, field_type)
    
    # Search with variations until we find results
    results = []
    for variation in variations[:5]:  # Try top 5 variations
        results = await search_web(variation, field_type)
        if results:
            break
    
    if not results:
        return {
            "verified": False,
            "confidence": 0,
            "match_type": "not_found",
            "top_result": None
        }
    
    # Score all results against original name AND variations
    scored_results = []
    for result in results:
        # Score against original
        original_score = score_result(result, name, field_type)
        
        # Score against variations (take best)
        variation_scores = [
            score_result(result, var, field_type) 
            for var in variations[:5]
        ]
        best_var_score = max(variation_scores, key=lambda x: x['confidence'])
        
        # Use better score
        final_score = (best_var_score if best_var_score['confidence'] > original_score['confidence'] 
                      else original_score)
        final_score['matched_variation'] = best_var_score['confidence'] > original_score['confidence']
        
        scored_results.append(final_score)
    
    # Return best match
    best = max(scored_results, key=lambda x: x['confidence'])
    best['verified'] = best['confidence'] >= 60
    
    return {
        "verified": best['verified'],
        "confidence": best['confidence'],
        "match_type": best['match_type'],
        "domain": best['domain'],
        "top_result": best['url'],
        "title": best['title'],
        "snippet": best['snippet'],
        "matched_variation": best.get('matched_variation', False)
    }


def extract_entities(profile: dict) -> dict:
    """Extract education and experience from LinkedIn profile"""
    educations = []
    experiences = []
    
    for edu in profile.get("educations", []):
        college = edu.get("title") or edu.get("subtitle") or edu.get("schoolName")
        if college:
            educations.append({"college": college})
    
    for exp in profile.get("experiences", []):
        company = exp.get("subtitle") or exp.get("companyName")
        position = exp.get("title") or "Unknown"
        if company:
            experiences.append({"company": company, "position": position})
    
    return {"educations": educations, "experiences": experiences}


async def verify_profile(profile: dict) -> dict:
    """
    Verify LinkedIn profile data
    
    THIS IS THE MAIN FUNCTION - Keep this signature unchanged!
    """
    entities = extract_entities(profile)
    
    # Verify education
    edu_tasks = [
        verify_entity(e["college"], "education") 
        for e in entities["educations"]
    ]
    edu_results = await asyncio.gather(*edu_tasks) if edu_tasks else []
    
    # Verify experience
    exp_tasks = [
        verify_entity(e["company"], "experience") 
        for e in entities["experiences"]
    ]
    exp_results = await asyncio.gather(*exp_tasks) if exp_tasks else []
    
    # Combine with original entities
    verified_edu = [
        {**entities["educations"][i], **edu_results[i]} 
        for i in range(len(edu_results))
    ]
    verified_exp = [
        {**entities["experiences"][i], **exp_results[i]} 
        for i in range(len(exp_results))
    ]
    
    # Compute scores
    edu_score = compute_score(verified_edu, "education")
    exp_score = compute_score(verified_exp, "experience")
    
    return {
        "profile_url": profile.get("publicIdentifier", "N/A"),
        "education": edu_score,
        "experience": exp_score
    }


def compute_score(entries: list, field_type: str) -> dict:
    """Compute overall verification score"""
    if not entries:
        return {
            "details": [], 
            "average_score": 0, 
            "overall_tag": "Not Found"
        }
    
    scored = []
    total = 0
    
    for entry in entries:
        confidence = entry.get("confidence", 0)
        verified = entry.get("verified", False)
        
        # Determine tag
        if confidence >= 75:
            tag = "Verified"
        elif confidence >= 60:
            tag = "Likely Match"
        elif confidence >= 40:
            tag = "Uncertain"
        else:
            tag = "Not Found"
        
        scored.append({
            **entry,
            "score": confidence,
            "tag": tag
        })
        total += confidence
    
    avg = round(total / len(scored), 2) if scored else 0
    
    # Overall tag
    if avg >= 75:
        overall = "Verified"
    elif avg >= 60:
        overall = "Likely Match"
    elif avg >= 40:
        overall = "Uncertain"
    else:
        overall = "Not Found"
    
    return {
        "details": scored,
        "average_score": avg,
        "overall_tag": overall
    }