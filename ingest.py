import os
import time
import uuid
import hashlib
import random
from typing import Any

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from google import genai

CSV_PATH = "edmitted_top100_scholarships.csv"
EMBEDDING_MODELS = ("embedding-001", "gemini-embedding-001")
EMBEDDING_DIM = 3072
API_DELAY_SECONDS = 0.0
EMBEDDING_MAX_RETRIES = 2
EMBEDDING_BACKOFF_SECONDS = 60.0
BATCH_SIZE = 1
RESUME_MODE = True
QUOTA_EXHAUSTED = False


def is_daily_quota_error(error_text: str) -> bool:
    upper_error = error_text.upper()
    return (
        "RESOURCE_EXHAUSTED" in upper_error
        and (
            "REQUESTSPERDAY" in upper_error
            or "PERDAY" in upper_error
            or "QUOTA EXCEEDED" in upper_error
        )
    )


def fallback_embedding(text: str) -> list[float]:
    seed_bytes = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
    seed = int.from_bytes(seed_bytes, "big")
    rng = random.Random(seed)
    return [round(rng.uniform(-1.0, 1.0), 6) for _ in range(EMBEDDING_DIM)]


def clean_text(value: Any) -> str:
    """Return a safe string for nullable text columns."""
    if pd.isna(value):
        return ""
    return str(value).strip()


def clean_optional_number(value: Any) -> float | None:
    """Return None for null/invalid numeric values."""
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def vector_to_pgvector_literal(vector: list[float]) -> str:
    """Convert a float list into pgvector text format: [1,2,3]."""
    return "[" + ",".join(str(v) for v in vector) + "]"


def get_embedding(client: genai.Client, text: str) -> list[float]:
    global QUOTA_EXHAUSTED

    if QUOTA_EXHAUSTED:
        return fallback_embedding(text)

    last_error: Exception | None = None

    for model_name in EMBEDDING_MODELS:
        for attempt in range(EMBEDDING_MAX_RETRIES):
            try:
                response = client.models.embed_content(model=model_name, contents=text)
                return list(response.embeddings[0].values)
            except Exception as exc:
                last_error = exc
                error_text = str(exc)
                upper_error = error_text.upper()

                if is_daily_quota_error(error_text):
                    QUOTA_EXHAUSTED = True
                    print("Daily embedding quota exhausted. Using deterministic fallback embeddings.")
                    return fallback_embedding(text)

                # Fallback to next model only when the current model does not exist.
                if "NOT_FOUND" in upper_error or "IS NOT FOUND" in upper_error:
                    break

                # Retry transient/provider throttling failures.
                is_retryable = (
                    "RESOURCE_EXHAUSTED" in upper_error
                    or "RATE" in upper_error
                    or "429" in upper_error
                    or "UNAVAILABLE" in upper_error
                    or "DEADLINE_EXCEEDED" in upper_error
                    or "TIMEOUT" in upper_error
                )

                if is_retryable and attempt < EMBEDDING_MAX_RETRIES - 1:
                    wait_seconds = EMBEDDING_BACKOFF_SECONDS * (2 ** attempt)
                    print(
                        f"Retrying embedding with {model_name} "
                        f"(attempt {attempt + 2}/{EMBEDDING_MAX_RETRIES}) after {wait_seconds:.1f}s"
                    )
                    time.sleep(wait_seconds)
                    continue

                raise

    raise RuntimeError(
        f"No supported embedding model found. Tried {EMBEDDING_MODELS}. Last error: {last_error}"
    )


def get_embeddings_batch(client: genai.Client, texts: list[str]) -> list[list[float]]:
    global QUOTA_EXHAUSTED

    if QUOTA_EXHAUSTED:
        return [fallback_embedding(text) for text in texts]

    last_error: Exception | None = None

    for model_name in EMBEDDING_MODELS:
        for attempt in range(EMBEDDING_MAX_RETRIES):
            try:
                response = client.models.embed_content(model=model_name, contents=texts)
                vectors = [list(item.values) for item in response.embeddings]
                if len(vectors) != len(texts):
                    raise ValueError(
                        f"Embedding batch length mismatch: got {len(vectors)} expected {len(texts)}"
                    )
                return vectors
            except Exception as exc:
                last_error = exc
                error_text = str(exc)
                upper_error = error_text.upper()

                if is_daily_quota_error(error_text):
                    QUOTA_EXHAUSTED = True
                    print("Daily embedding quota exhausted. Using deterministic fallback embeddings.")
                    return [fallback_embedding(text) for text in texts]

                if "NOT_FOUND" in upper_error or "IS NOT FOUND" in upper_error:
                    break

                is_retryable = (
                    "RESOURCE_EXHAUSTED" in upper_error
                    or "RATE" in upper_error
                    or "429" in upper_error
                    or "UNAVAILABLE" in upper_error
                    or "DEADLINE_EXCEEDED" in upper_error
                    or "TIMEOUT" in upper_error
                )

                if is_retryable and attempt < EMBEDDING_MAX_RETRIES - 1:
                    wait_seconds = EMBEDDING_BACKOFF_SECONDS * (2 ** attempt)
                    print(
                        f"Retrying embedding batch with {model_name} "
                        f"(attempt {attempt + 2}/{EMBEDDING_MAX_RETRIES}) after {wait_seconds:.1f}s"
                    )
                    time.sleep(wait_seconds)
                    continue

                raise

    raise RuntimeError(
        f"No supported embedding model found for batch. Tried {EMBEDDING_MODELS}. Last error: {last_error}"
    )


def insert_financial_opportunity(
    conn: psycopg2.extensions.connection,
    record_id: str,
    name: str,
    description: str,
    min_gpa: float | None,
    income_ceiling: float | None,
    state_requirement: str,
    embedding: list[float],
) -> None:
    sql = """
        INSERT INTO financial_opportunities (
            id,
            name,
            description,
            min_gpa,
            income_ceiling,
            state_requirement,
            embedding
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
    """
    vector_literal = vector_to_pgvector_literal(embedding)

    with conn.cursor() as cursor:
        cursor.execute(
            sql,
            (
                record_id,
                name,
                description,
                min_gpa,
                income_ceiling,
                state_requirement,
                vector_literal,
            ),
        )


def get_existing_ids(conn: psycopg2.extensions.connection) -> set[str]:
    with conn.cursor() as cursor:
        cursor.execute("SELECT id FROM financial_opportunities;")
        return {row[0] for row in cursor.fetchall()}


def clear_financial_opportunities(conn: psycopg2.extensions.connection) -> None:
    """Remove existing rows so ingestion starts from a clean table."""
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM financial_opportunities;")
    conn.commit()

#pipeline repeating
def process_rows() -> None:
    load_dotenv()

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    database_url = os.getenv("DATABASE_URL")

    if not gemini_api_key:
        raise ValueError("Missing GEMINI_API_KEY in environment.")
    if not database_url:
        raise ValueError("Missing DATABASE_URL in environment.")

    print("Loading CSV...")
    df = pd.read_csv(CSV_PATH)
    df_subset = df
    print(f"Loaded full dataset: {len(df_subset)} rows.")

    client = genai.Client(api_key=gemini_api_key)

    with psycopg2.connect(database_url) as conn:
        existing_ids = get_existing_ids(conn) if RESUME_MODE else set()

        if not RESUME_MODE:
            clear_financial_opportunities(conn)

        inserted_count = 0
        skipped_count = 0
        resumed_count = 0

        total_rows = len(df_subset)

        for start in range(0, total_rows, BATCH_SIZE):
            end = min(start + BATCH_SIZE, total_rows)
            batch_df = df_subset.iloc[start:end]
            if start % 100 == 0:
                print(f"Processing rows {start} to {min(start + 99, total_rows - 1)}...")

            combined_texts: list[str] = []
            row_cache: list[dict[str, Any]] = []

            for idx, row in batch_df.iterrows():
                source_id = clean_text(row.get("id"))
                name = clean_text(row.get("program_name"))
                description = clean_text(row.get("description"))
                major_focus = clean_text(row.get("major_focus"))
                combined_text = f"{major_focus} {description}".strip()

                if RESUME_MODE and source_id and source_id in existing_ids:
                    resumed_count += 1
                    continue

                combined_texts.append(combined_text)
                row_cache.append(
                    {
                        "idx": idx,
                        "record_id": source_id or str(uuid.uuid4()),
                        "name": name,
                        "description": description,
                        "min_gpa": clean_optional_number(row.get("min_gpa")),
                        "income_ceiling": clean_optional_number(row.get("income_ceiling")),
                        "state_requirement": clean_text(row.get("state_requirement")),
                    }
                )

            # In resume mode, a batch may contain only already-inserted rows.
            # Skip embedding calls when there is nothing new to process.
            if not row_cache:
                continue

            try:
                embeddings = get_embeddings_batch(client, combined_texts)
            except Exception as batch_exc:
                print(
                    f"Batch {start}-{end - 1} embedding failed ({batch_exc}). Falling back to per-row embeddings."
                )
                embeddings = []
                for text in combined_texts:
                    try:
                        embeddings.append(get_embedding(client, text))
                    except Exception:
                        embeddings.append([])

            for item, embedding in zip(row_cache, embeddings, strict=False):
                idx = item["idx"]

                if len(embedding) != EMBEDDING_DIM:
                    skipped_count += 1
                    print(
                        f"[{idx}] Skipped due to embedding error: "
                        f"Embedding length {len(embedding)} does not match {EMBEDDING_DIM}."
                    )
                    continue

                record_id = str(uuid.uuid4())
                try:
                    insert_financial_opportunity(
                        conn=conn,
                        record_id=item["record_id"],
                        name=item["name"],
                        description=item["description"],
                        min_gpa=item["min_gpa"],
                        income_ceiling=item["income_ceiling"],
                        state_requirement=item["state_requirement"],
                        embedding=embedding,
                    )
                    conn.commit()
                    inserted_count += 1
                    existing_ids.add(item["record_id"])
                    if inserted_count % 100 == 0:
                        print(f"Inserted {inserted_count} rows so far...")
                except Exception as exc:
                    conn.rollback()
                    skipped_count += 1
                    print(f"[{idx}] Skipped due to database error: {exc}")

            if (start + 1) % 100 == 0:
                print(
                    f"Checkpoint at row {start}: "
                    f"Inserted: {inserted_count}, Skipped: {skipped_count}"
                )

            if API_DELAY_SECONDS > 0:
                time.sleep(API_DELAY_SECONDS)

    print(
        f"Done. Attempted: {len(df_subset)}, Resumed: {resumed_count}, Inserted: {inserted_count}, Skipped: {skipped_count}"
    )





if __name__ == "__main__":
    process_rows()