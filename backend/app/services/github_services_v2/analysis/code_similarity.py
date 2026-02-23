"""
Enterprise GitHub Verification — Code Clone Detection
Uses CodeBERT (microsoft/codebert-base) for code-level similarity.

Pipeline:
  1. File tree extraction (GitHub Trees API, recursive)
  2. Filter by extension, exclude dirs, enforce limits
  3. Fetch + normalise code (remove comments, headers, whitespace)
  4. Structural pre-filter (Jaccard on file paths ≥ 0.25)
  5. Chunk (1500c, newline boundaries, drop <200c)
  6. Embed with CodeBERT (cached: LRU in-memory + optional disk)
  7. Per-chunk max similarity, top-30% average → repo sim
  8. codeSimilarityMax = max across reference repos
  9. CodeOriginality = 1 - codeSimilarityMax
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from ..config import (
    CODEBERT_MODEL,
    CODEBERT_EMBEDDING_DIM,
    CODE_CHUNK_MIN_SIZE,
    CODE_CHUNK_SIZE,
    CODE_SIMILARITY_COPIED,
    CODE_SIMILARITY_SUSPICIOUS,
    DEEP_ANALYSIS_TIMEOUT_SECONDS,
    DEVICE,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_CACHE_DIR,
    EMBEDDING_CACHE_TTL_HOURS,
    EMBEDDING_LRU_MAX_SIZE,
    EXCLUDED_DIRECTORIES,
    MAX_CODE_FILE_SIZE_BYTES,
    MAX_CODE_FILES_PER_REPO,
    MAX_EXTERNAL_REPOS,
    MAX_TOTAL_CODE_SIZE_BYTES,
    NUM_THREADS,
    STRUCTURE_JACCARD_THRESHOLD,
    SUPPORTED_CODE_EXTENSIONS,
    TOP_CHUNK_PERCENT,
)
from ..github_client import GitHubClient

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# Guaranteed singleton CodeBERT loader
# ═══════════════════════════════════════════════════════════════════

_codebert_model = None
_codebert_tokenizer = None
_codebert_lock: Optional[asyncio.Lock] = None


def _get_codebert_lock() -> asyncio.Lock:
    global _codebert_lock
    if _codebert_lock is None:
        _codebert_lock = asyncio.Lock()
    return _codebert_lock


async def _ensure_codebert():
    """Lazy-load CodeBERT model exactly once. Double-check locking."""
    global _codebert_model, _codebert_tokenizer
    if _codebert_model is not None:
        return

    lock = _get_codebert_lock()
    async with lock:
        if _codebert_model is not None:
            return

        def _load():
            global _codebert_model, _codebert_tokenizer
            import torch
            from transformers import AutoModel, AutoTokenizer

            torch.set_num_threads(NUM_THREADS)
            _codebert_tokenizer = AutoTokenizer.from_pretrained(CODEBERT_MODEL)
            _codebert_model = AutoModel.from_pretrained(CODEBERT_MODEL)
            _codebert_model.to(DEVICE)
            _codebert_model.eval()
            logger.info("CodeBERT model loaded: %s", CODEBERT_MODEL)

        await asyncio.to_thread(_load)


# ═══════════════════════════════════════════════════════════════════
# In-memory LRU embedding cache + optional disk cache
# ═══════════════════════════════════════════════════════════════════

class _EmbeddingCache:
    """In-memory LRU + optional disk at EMBEDDING_CACHE_DIR. Key = SHA256(text)."""

    def __init__(self):
        self._mem: OrderedDict[str, np.ndarray] = OrderedDict()
        os.makedirs(EMBEDDING_CACHE_DIR, exist_ok=True)

    def _key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> Optional[np.ndarray]:
        key = self._key(text)
        # memory
        if key in self._mem:
            self._mem.move_to_end(key)
            return self._mem[key]
        # disk
        path = os.path.join(EMBEDDING_CACHE_DIR, f"{key}.npy")
        meta_path = os.path.join(EMBEDDING_CACHE_DIR, f"{key}.meta")
        if os.path.exists(path) and os.path.exists(meta_path):
            try:
                with open(meta_path, "r") as f:
                    ts = datetime.fromisoformat(f.read().strip())
                if datetime.now() - ts > timedelta(hours=EMBEDDING_CACHE_TTL_HOURS):
                    os.remove(path)
                    os.remove(meta_path)
                    return None
                emb = np.load(path)
                self._put_mem(key, emb)
                return emb
            except Exception:
                return None
        return None

    def put(self, text: str, emb: np.ndarray) -> None:
        key = self._key(text)
        self._put_mem(key, emb)
        # disk persist
        try:
            np.save(os.path.join(EMBEDDING_CACHE_DIR, f"{key}.npy"), emb)
            with open(os.path.join(EMBEDDING_CACHE_DIR, f"{key}.meta"), "w") as f:
                f.write(datetime.now().isoformat())
        except Exception:
            pass

    def _put_mem(self, key: str, emb: np.ndarray) -> None:
        if key in self._mem:
            self._mem.move_to_end(key)
        else:
            self._mem[key] = emb
            if len(self._mem) > EMBEDDING_LRU_MAX_SIZE:
                self._mem.popitem(last=False)


_embedding_cache = _EmbeddingCache()


# ═══════════════════════════════════════════════════════════════════
# Code normalisation
# ═══════════════════════════════════════════════════════════════════

_RE_SINGLE_LINE = re.compile(r"(//.*?$|#.*?$)", re.MULTILINE)
_RE_MULTI_LINE = re.compile(r'/\*.*?\*/|""".*?"""|\'\'\'.*?\'\'\'', re.DOTALL)
_RE_LICENSE = re.compile(r"\A\s*(?:(?://|#|/\*|\*|\"\"\"|''').*\n){2,15}", re.MULTILINE)
_RE_EXCESS_NL = re.compile(r"\n{3,}")
_RE_TRAILING = re.compile(r"[ \t]+$", re.MULTILINE)


def _normalise_code(code: str) -> str:
    """
    Remove license header, all comments, trailing whitespace, excessive
    blank lines.  Preserve indentation + function names + structure.
    """
    code = _RE_LICENSE.sub("", code)
    code = _RE_MULTI_LINE.sub("", code)
    code = _RE_SINGLE_LINE.sub("", code)
    code = _RE_TRAILING.sub("", code)
    code = _RE_EXCESS_NL.sub("\n\n", code)
    return code.strip()


def _ext_to_lang(path: str) -> str:
    mapping = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".java": "java", ".cpp": "cpp", ".c": "c", ".go": "go",
        ".cs": "csharp", ".php": "php", ".rb": "ruby",
    }
    ext = os.path.splitext(path)[1].lower()
    return mapping.get(ext, "unknown")


# ═══════════════════════════════════════════════════════════════════
# Chunking
# ═══════════════════════════════════════════════════════════════════

def _chunk_code(code: str) -> List[str]:
    """Split into chunks of CODE_CHUNK_SIZE chars, prefer newline boundaries."""
    chunks: List[str] = []
    while len(code) > CODE_CHUNK_SIZE:
        # Find last newline within window
        cut = code[:CODE_CHUNK_SIZE].rfind("\n")
        if cut <= 0:
            cut = CODE_CHUNK_SIZE
        chunks.append(code[:cut])
        code = code[cut:].lstrip("\n")
    if code:
        chunks.append(code)
    # Drop small chunks
    return [c for c in chunks if len(c) >= CODE_CHUNK_MIN_SIZE]


# ═══════════════════════════════════════════════════════════════════
# Embedding helper
# ═══════════════════════════════════════════════════════════════════

async def _embed_chunks(chunks: List[str]) -> np.ndarray:
    """Embed code chunks with CodeBERT. Uses LRU + disk cache."""
    await _ensure_codebert()

    cached_results: Dict[int, np.ndarray] = {}
    to_encode: List[Tuple[int, str]] = []

    for i, chunk in enumerate(chunks):
        cached = _embedding_cache.get(chunk)
        if cached is not None:
            cached_results[i] = cached
        else:
            to_encode.append((i, chunk))

    # Batch encode uncached
    if to_encode:
        texts = [t for _, t in to_encode]

        def _encode_batch():
            import torch
            all_embs = []
            for b_start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
                batch = texts[b_start : b_start + EMBEDDING_BATCH_SIZE]
                encoded = _codebert_tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=512,
                    return_tensors="pt",
                )
                with torch.no_grad():
                    outputs = _codebert_model(**encoded)
                # CLS pooling
                embs = outputs.last_hidden_state[:, 0, :].cpu().numpy()
                # L2 normalise
                norms = np.linalg.norm(embs, axis=1, keepdims=True)
                norms[norms == 0] = 1.0
                embs = embs / norms
                all_embs.append(embs)
            return np.vstack(all_embs) if all_embs else np.empty((0, CODEBERT_EMBEDDING_DIM))

        new_embs = await asyncio.to_thread(_encode_batch)
        for j, (idx, text) in enumerate(to_encode):
            emb = new_embs[j]
            _embedding_cache.put(text, emb)
            cached_results[idx] = emb

    # Reassemble in original order
    return np.array([cached_results[i] for i in range(len(chunks))])


# ═══════════════════════════════════════════════════════════════════
# File tree filtering
# ═══════════════════════════════════════════════════════════════════

def _filter_code_files(tree: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter tree entries to supported code files within guardrails."""
    files: List[Dict[str, Any]] = []
    total_size = 0

    for entry in tree:
        if entry.get("type") != "blob":
            continue
        path = entry.get("path", "")
        size = entry.get("size", 0)

        # Extension check
        ext = os.path.splitext(path)[1].lower()
        if ext not in SUPPORTED_CODE_EXTENSIONS:
            continue

        # Excluded directory check
        if any(excl in path.split("/") for excl in EXCLUDED_DIRECTORIES):
            continue

        # Size guards
        if size > MAX_CODE_FILE_SIZE_BYTES:
            continue
        if total_size + size > MAX_TOTAL_CODE_SIZE_BYTES:
            break  # hard stop
        if len(files) >= MAX_CODE_FILES_PER_REPO:
            break

        files.append({"path": path, "size": size})
        total_size += size

    return files


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


# ═══════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════

async def analyse_code_similarity(
    repos: List[Dict[str, Any]],
    client: GitHubClient,
) -> Dict[str, Any]:
    """
    Run code clone detection for *repos* (max 3).

    Returns::

        {
            "codeSimilarityMax": float,
            "codeVerdict": str,
            "codeMatchedRepo": str | None,
            "codeOriginality": float,
            "repoDetails": [...]
        }
    """
    if client.rate_limited:
        return _empty_result("Skipped: GitHub rate-limited")

    overall_max_sim: float = 0.0
    overall_matched: Optional[str] = None
    repo_details: List[Dict[str, Any]] = []

    for repo in repos:
        owner = repo.get("owner", {})
        owner_login = owner.get("login", owner) if isinstance(owner, dict) else str(owner)
        repo_name = repo.get("name", "")

        try:
            detail = await asyncio.wait_for(
                _analyse_single_repo(owner_login, repo_name, client),
                timeout=DEEP_ANALYSIS_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            detail = {
                "repo": repo_name,
                "similarity": 0.0,
                "verdict": "ORIGINAL",
                "matchedRepo": None,
                "skipped": True,
                "reason": "Timeout exceeded",
            }
        except Exception as exc:
            detail = {
                "repo": repo_name,
                "similarity": 0.0,
                "verdict": "ORIGINAL",
                "matchedRepo": None,
                "skipped": True,
                "reason": str(exc),
            }

        repo_details.append(detail)
        sim = detail.get("similarity", 0.0)
        if sim > overall_max_sim:
            overall_max_sim = sim
            overall_matched = detail.get("matchedRepo")

    originality = max(0.0, min(1.0, 1.0 - overall_max_sim))
    return {
        "codeSimilarityMax": round(overall_max_sim, 4),
        "codeVerdict": _verdict(overall_max_sim),
        "codeMatchedRepo": overall_matched,
        "codeOriginality": round(originality, 4),
        "repoDetails": repo_details,
    }


async def _analyse_single_repo(
    owner: str,
    repo_name: str,
    client: GitHubClient,
) -> Dict[str, Any]:
    """Run code clone detection on a single repo."""

    # 1. Get default branch
    repo_info = await client.get_repo_info(owner, repo_name)
    default_branch = "HEAD"
    if repo_info:
        default_branch = repo_info.get("default_branch", "HEAD")

    # 2. File tree
    tree = await client.get_repo_tree(owner, repo_name, branch=default_branch)
    cand_files = _filter_code_files(tree)
    if not cand_files:
        return _skip(repo_name, "No code files found")

    # 3. Fetch + normalise candidate code
    cand_code_blocks: List[str] = []
    cand_paths: Set[str] = set()
    for f in cand_files:
        content = await client.get_file_content(owner, repo_name, f["path"])
        if content:
            norm = _normalise_code(content)
            if norm:
                lang = _ext_to_lang(f["path"])
                block = f"FILE_PATH: {f['path']}\nLANGUAGE: {lang}\nCONTENT:\n{norm}"
                cand_code_blocks.append(block)
                cand_paths.add(f["path"])

    if not cand_code_blocks:
        return _skip(repo_name, "No normalisable code")

    cand_text = "\n\n".join(cand_code_blocks)
    cand_chunks = _chunk_code(cand_text)
    if not cand_chunks:
        return _skip(repo_name, "No valid chunks after splitting")

    # 4. Search similar external repos
    ext_repos = await client.search_similar_repos(repo_name, limit=MAX_EXTERNAL_REPOS)
    ext_repos = [r for r in ext_repos if r.get("full_name", "") != f"{owner}/{repo_name}"]
    if not ext_repos:
        return _skip(repo_name, "No external repos found")

    # 5. Embed candidate chunks
    cand_embs = await _embed_chunks(cand_chunks)

    # 6. Compare against each reference repo
    max_repo_sim = 0.0
    matched_ref: Optional[str] = None

    for ref in ext_repos:
        ref_owner = ref["owner"]
        ref_name = ref["name"]

        # Get ref tree
        ref_info = await client.get_repo_info(ref_owner, ref_name)
        ref_branch = ref_info.get("default_branch", "HEAD") if ref_info else "HEAD"
        ref_tree = await client.get_repo_tree(ref_owner, ref_name, branch=ref_branch)
        ref_files = _filter_code_files(ref_tree)
        if not ref_files:
            continue

        ref_paths = {f["path"] for f in ref_files}

        # Structural pre-filter
        j = _jaccard(cand_paths, ref_paths)
        if j < STRUCTURE_JACCARD_THRESHOLD:
            continue

        # Fetch + normalise ref code
        ref_code_blocks: List[str] = []
        for f in ref_files:
            content = await client.get_file_content(ref_owner, ref_name, f["path"])
            if content:
                norm = _normalise_code(content)
                if norm:
                    lang = _ext_to_lang(f["path"])
                    block = f"FILE_PATH: {f['path']}\nLANGUAGE: {lang}\nCONTENT:\n{norm}"
                    ref_code_blocks.append(block)

        if not ref_code_blocks:
            continue

        ref_text = "\n\n".join(ref_code_blocks)
        ref_chunks = _chunk_code(ref_text)
        if not ref_chunks:
            continue

        ref_embs = await _embed_chunks(ref_chunks)

        # 7. Similarity: per candidate chunk → max vs ref chunks
        # Then top 30% average
        chunk_max_sims: List[float] = []
        for c_emb in cand_embs:
            sims = ref_embs @ c_emb  # dot product
            chunk_max_sims.append(float(np.max(sims)) if len(sims) > 0 else 0.0)

        chunk_max_sims.sort(reverse=True)
        top_n = max(1, int(len(chunk_max_sims) * TOP_CHUNK_PERCENT))
        repo_sim = float(np.mean(chunk_max_sims[:top_n]))

        if repo_sim > max_repo_sim:
            max_repo_sim = repo_sim
            matched_ref = ref.get("full_name", "")

    return {
        "repo": repo_name,
        "similarity": round(max(0.0, min(1.0, max_repo_sim)), 4),
        "verdict": _verdict(max_repo_sim),
        "matchedRepo": matched_ref,
        "skipped": False,
    }


def _verdict(sim: float) -> str:
    if sim >= CODE_SIMILARITY_COPIED:
        return "COPIED"
    if sim >= CODE_SIMILARITY_SUSPICIOUS:
        return "SUSPICIOUS"
    return "ORIGINAL"


def _skip(repo: str, reason: str) -> Dict[str, Any]:
    return {
        "repo": repo,
        "similarity": 0.0,
        "verdict": "ORIGINAL",
        "matchedRepo": None,
        "skipped": True,
        "reason": reason,
    }


def _empty_result(reason: str) -> Dict[str, Any]:
    return {
        "codeSimilarityMax": 0.0,
        "codeVerdict": "ORIGINAL",
        "codeMatchedRepo": None,
        "codeOriginality": 1.0,
        "repoDetails": [{"skipped": True, "reason": reason}],
    }
