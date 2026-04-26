import hashlib
import random
import time
import math
import re

import psycopg2

EMBEDDING_MODELS = ("gemini-embedding-001", "embedding-001")
EMBEDDING_DIM = 3072
EMBEDDING_MAX_RETRIES = 2
EMBEDDING_RETRY_BACKOFF_SECONDS = 2.0
LAST_EMBEDDING_USED_FALLBACK = False


def fallback_embedding(text: str) -> list[float]:
    """Deterministic token-hash embedding that preserves lexical overlap when provider quota is exhausted."""
    vec = [0.0] * EMBEDDING_DIM
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    if not tokens:
        return vec

    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8", errors="ignore")).digest()
        idx = int.from_bytes(digest[:2], "big") % EMBEDDING_DIM
        sign = -1.0 if (digest[2] % 2) else 1.0
        vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec

    return [round(v / norm, 6) for v in vec]


def embedding_fallback_active() -> bool:
    return LAST_EMBEDDING_USED_FALLBACK


def is_not_found_error(error_text: str) -> bool:
    upper_text = error_text.upper()
    return "NOT_FOUND" in upper_text or "IS NOT FOUND" in upper_text


def is_resource_exhausted_error(error_text: str) -> bool:
    upper_text = error_text.upper()
    return "RESOURCE_EXHAUSTED" in upper_text or "429" in upper_text or "QUOTA" in upper_text

def vector_to_pgvector_literal(vector: list[float]) -> str:
    """Convert a Python list of floats into a string like '[0.1, 0.2, ...]'."""
    return "[" + ",".join(str(x) for x in vector) + "]"

def get_embedding(client, text: str) -> list[float]:
    global LAST_EMBEDDING_USED_FALLBACK

    LAST_EMBEDDING_USED_FALLBACK = False
    last_error: Exception | None = None

    for model_name in EMBEDDING_MODELS:
        for attempt in range(EMBEDDING_MAX_RETRIES):
            try:
                response = client.models.embed_content(
                    model=model_name,
                    contents=text,
                )
                return list(response.embeddings[0].values)
            except Exception as exc:
                last_error = exc
                error_text = str(exc)

                if is_not_found_error(error_text):
                    break

                if is_resource_exhausted_error(error_text):
                    LAST_EMBEDDING_USED_FALLBACK = True
                    return fallback_embedding(text)

                if attempt < EMBEDDING_MAX_RETRIES - 1:
                    time.sleep(EMBEDDING_RETRY_BACKOFF_SECONDS * (2 ** attempt))
                    continue

    # Keep API available even when embedding provider is unstable.
    LAST_EMBEDDING_USED_FALLBACK = True
    return fallback_embedding(text)

def get_student_embedding(client, major: str, extracurriculars: str) -> list[float]:
    text = f"Major: {major} {extracurriculars}".strip()
    return get_embedding(client, text)

def get_all_eligible_scholarships(conn, embedding: list[float], search_text: str, gpa: float, income: float, state: str):
    sql = """
        SELECT id, name, description,
               embedding <=> %s AS distance,
               ts_rank(to_tsvector('english', coalesce(name, '') || ' ' || coalesce(description, '')), websearch_to_tsquery('english', %s)) AS text_rank,
               income_ceiling
        FROM financial_opportunities
        WHERE
            min_gpa IS NOT NULL
            AND min_gpa <= %s
            AND (income_ceiling IS NULL OR income_ceiling >= %s)
            AND (state_requirement = %s OR state_requirement = 'National')
    """
    vector_literal = vector_to_pgvector_literal(embedding)
    with conn.cursor() as cursor:
        cursor.execute(sql, (vector_literal, search_text, gpa, income, state))
        return cursor.fetchall()
