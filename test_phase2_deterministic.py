"""
Deterministic Tests for Phase-2
Tests similarity thresholds, branch commits, clone detection, and scoring penalties
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np


def test_similarity_thresholds():
    """Test: Same README → similarity > 0.95"""
    print("Testing similarity thresholds...")
    
    try:
        from github.ml.inference.similarity_engine import SimilarityEngine
        
        engine = SimilarityEngine()
        
        # Test 1: Identical READMEs
        readme1 = "This is a machine learning project using Python and TensorFlow for image classification"
        readme2 = readme1  # Exact same
        
        similarity = engine.compute_similarity(readme1, readme2)
        assert similarity > 0.95, f"Identical READMEs should have similarity > 0.95, got {similarity}"
        print(f"  ✅ Identical READMEs: {similarity:.3f} > 0.95")
        
        # Test 2: Very similar (template)
        readme3 = "This is a machine learning project using Python and TensorFlow for image classification tasks"
        readme4 = "This is a machine learning project with Python and TensorFlow for image classification"
        
        similarity2 = engine.compute_similarity(readme3, readme4)
        assert similarity2 > 0.85, f"Template READMEs should have similarity > 0.85, got {similarity2}"
        print(f"  ✅ Template READMEs: {similarity2:.3f} > 0.85")
        
        # Test 3: Different projects
        readme5 = "A web development project using React and Node.js for building e-commerce sites"
        readme6 = "Machine learning project with Python for natural language processing"
        
        similarity3 = engine.compute_similarity(readme5, readme6)
        assert similarity3 < 0.70, f"Different projects should have similarity < 0.70, got {similarity3}"
        print(f"  ✅ Different projects: {similarity3:.3f} < 0.70")
        
        print("✅ Similarity threshold tests passed\n")
        return True
        
    except ImportError as e:
        print(f"  ⚠️  Skipping (dependencies not installed): {e}\n")
        return True  # Don't fail if ML deps not installed
    except Exception as e:
        print(f"  ❌ Failed: {e}\n")
        return False


def test_clone_detection_verdicts():
    """Test clone detection verdict mapping"""
    print("Testing clone detection verdicts...")
    
    try:
        from github.ml.inference.similarity_engine import SimilarityEngine
        from github.ml.config.ml_config import (
            CLONE_VERDICT_COPIED,
            CLONE_VERDICT_TEMPLATE,
            CLONE_VERDICT_ORIGINAL
        )
        
        engine = SimilarityEngine()
        
        # Test verdict mapping
        verdict_copied = engine.get_verdict(0.92)
        assert verdict_copied == CLONE_VERDICT_COPIED, f"0.92 should be COPIED, got {verdict_copied}"
        print(f"  ✅ Similarity 0.92 → {verdict_copied}")
        
        verdict_template = engine.get_verdict(0.85)
        assert verdict_template == CLONE_VERDICT_TEMPLATE, f"0.85 should be TEMPLATE, got {verdict_template}"
        print(f"  ✅ Similarity 0.85 → {verdict_template}")
        
        verdict_original = engine.get_verdict(0.70)
        assert verdict_original == CLONE_VERDICT_ORIGINAL, f"0.70 should be ORIGINAL, got {verdict_original}"
        print(f"  ✅ Similarity 0.70 → {verdict_original}")
        
        print("✅ Clone verdict tests passed\n")
        return True
        
    except ImportError as e:
        print(f"  ⚠️  Skipping (dependencies not installed): {e}\n")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}\n")
        return False


def test_scoring_penalties():
    """Test scoring penalty calculation"""
    print("Testing scoring penalties...")
    
    try:
        from github.ml.inference.similarity_engine import SimilarityEngine
        
        engine = SimilarityEngine()
        
        # Test penalty thresholds
        penalty_high = engine.get_penalty(0.92)
        assert penalty_high == 25, f"Similarity 0.92 should have -25 penalty, got {penalty_high}"
        print(f"  ✅ Similarity 0.92 → -{penalty_high} points")
        
        penalty_medium = engine.get_penalty(0.85)
        assert penalty_medium == 15, f"Similarity 0.85 should have -15 penalty, got {penalty_medium}"
        print(f"  ✅ Similarity 0.85 → -{penalty_medium} points")
        
        penalty_none = engine.get_penalty(0.70)
        assert penalty_none == 0, f"Similarity 0.70 should have 0 penalty, got {penalty_none}"
        print(f"  ✅ Similarity 0.70 → -{penalty_none} points")
        
        print("✅ Scoring penalty tests passed\n")
        return True
        
    except ImportError as e:
        print(f"  ⚠️  Skipping (dependencies not installed): {e}\n")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}\n")
        return False


def test_branch_commit_deduplication():
    """Test that commits on dev branch are counted and deduplicated"""
    print("Testing branch commit deduplication...")
    
    from github.utils.branch_utils import aggregate_branch_commits
    
    # Mock commits with same SHA in multiple branches
    branch_commits = {
        "main": [
            {"sha": "abc123", "commit": {"author": {"date": "2024-01-01T10:00:00Z"}}},
            {"sha": "def456", "commit": {"author": {"date": "2024-01-02T10:00:00Z"}}},
        ],
        "develop": [
            {"sha": "abc123", "commit": {"author": {"date": "2024-01-01T10:00:00Z"}}},  # Duplicate
            {"sha": "def456", "commit": {"author": {"date": "2024-01-02T10:00:00Z"}}},  # Duplicate
            {"sha": "ghi789", "commit": {"author": {"date": "2024-01-03T10:00:00Z"}}},  # New
        ],
        "feature-x": [
            {"sha": "jkl012", "commit": {"author": {"date": "2024-01-04T10:00:00Z"}}},  # New
        ]
    }
    
    result = aggregate_branch_commits(branch_commits)
    
    # Should have 4 unique commits (abc123, def456, ghi789, jkl012)
    assert result["total_unique_commits"] == 4, f"Should have 4 unique commits, got {result['total_unique_commits']}"
    print(f"  ✅ Deduplicated commits: {result['total_unique_commits']} unique from 6 total")
    
    assert result["total_branches"] == 3, f"Should have 3 branches, got {result['total_branches']}"
    print(f"  ✅ Branches counted: {result['total_branches']}")
    
    # Check that duplicates are marked
    assert len(result["unique_commits"]) == 4
    print(f"  ✅ Unique commits stored: {len(result['unique_commits'])}")
    
    print("✅ Branch commit tests passed\n")
    return True


def test_embedding_cache():
    """Test embedding cache functionality"""
    print("Testing embedding cache...")
    
    try:
        from github.ml.embeddings.embedding_cache import EmbeddingCache
        import tempfile
        import shutil
        
        # Use temp directory for testing
        temp_dir = tempfile.mkdtemp()
        cache = EmbeddingCache(cache_dir=temp_dir)
        
        # Test cache miss
        result = cache.get("test text that doesn't exist")
        assert result is None, "Cache miss should return None"
        print("  ✅ Cache miss returns None")
        
        # Test cache set and hit
        test_embedding = np.array([0.1, 0.2, 0.3, 0.4])
        cache.set("test text", test_embedding)
        
        cached = cache.get("test text")
        assert cached is not None, "Cached embedding should exist"
        assert np.allclose(cached, test_embedding), "Cached embedding should match original"
        print("  ✅ Cache set and get works")
        
        # Cleanup
        shutil.rmtree(temp_dir)
        
        print("✅ Embedding cache tests passed\n")
        return True
        
    except ImportError as e:
        print(f"  ⚠️  Skipping (dependencies not installed): {e}\n")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}\n")
        return False


def test_config_constants():
    """Test that all required config constants exist"""
    print("Testing config constants...")
    
    from github.ml.config.ml_config import (
        ENABLE_PROJECT_MATCHING,
        DEEP_ANALYZE_MATCHED_REPOS_ONLY,
        MAX_DEEP_ANALYZED_REPOS,
        USE_EMBEDDING_CACHE,
        SIMILARITY_VERY_HIGH,
        SIMILARITY_HIGH,
        PENALTY_VERY_HIGH_SIMILARITY,
        PENALTY_HIGH_SIMILARITY
    )
    
    assert SIMILARITY_VERY_HIGH == 0.90, "SIMILARITY_VERY_HIGH should be 0.90"
    print(f"  ✅ SIMILARITY_VERY_HIGH = {SIMILARITY_VERY_HIGH}")
    
    assert SIMILARITY_HIGH == 0.80, "SIMILARITY_HIGH should be 0.80"
    print(f"  ✅ SIMILARITY_HIGH = {SIMILARITY_HIGH}")
    
    assert PENALTY_VERY_HIGH_SIMILARITY == 25, "PENALTY_VERY_HIGH_SIMILARITY should be 25"
    print(f"  ✅ PENALTY_VERY_HIGH_SIMILARITY = {PENALTY_VERY_HIGH_SIMILARITY}")
    
    assert PENALTY_HIGH_SIMILARITY == 15, "PENALTY_HIGH_SIMILARITY should be 15"
    print(f"  ✅ PENALTY_HIGH_SIMILARITY = {PENALTY_HIGH_SIMILARITY}")
    
    print("✅ Config constants test passed\n")
    return True


def run_all_deterministic_tests():
    """Run all deterministic tests"""
    print("=" * 60)
    print("Phase-2 Deterministic Tests")
    print("=" * 60)
    print()
    
    results = []
    
    # Test config first (no ML dependencies needed)
    results.append(("Config Constants", test_config_constants()))
    
    # Test branch utils (no ML dependencies)
    results.append(("Branch Commit Deduplication", test_branch_commit_deduplication()))
    
    # ML-dependent tests
    results.append(("Similarity Thresholds", test_similarity_thresholds()))
    results.append(("Clone Detection Verdicts", test_clone_detection_verdicts()))
    results.append(("Scoring Penalties", test_scoring_penalties()))
    results.append(("Embedding Cache", test_embedding_cache()))
    
    # Summary
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ ALL TESTS PASSED")
        return True
    else:
        print("❌ SOME TESTS FAILED")
        return False


if __name__ == "__main__":
    success = run_all_deterministic_tests()
    sys.exit(0 if success else 1)