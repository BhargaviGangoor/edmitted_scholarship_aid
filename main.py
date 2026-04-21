import os
import time
import uuid
from typing import Any

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from google import genai

CSV_PATH = "edmitted_top100_scholarships.csv"
EMBEDDING_MODELS = ("embedding-001", "gemini-embedding-001")
EMBEDDING_DIM = 3072
API_DELAY_SECONDS = 1.0


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
    last_error: Exception | None = None

    for model_name in EMBEDDING_MODELS:
        try:
            response = client.models.embed_content(model=model_name, contents=text)
            return list(response.embeddings[0].values)
        except Exception as exc:
            last_error = exc
            error_text = str(exc)

            # Keep fallback narrow to known model-not-found responses.
            if "NOT_FOUND" not in error_text and "is not found" not in error_text:
                raise

    raise RuntimeError(
        f"No supported embedding model found. Tried {EMBEDDING_MODELS}. Last error: {last_error}"
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

    with psycopg2.connect(database_url, sslmode="require") as conn:
        clear_financial_opportunities(conn)

        inserted_count = 0
        skipped_count = 0

        for idx, row in df_subset.iterrows():
            name = clean_text(row.get("program_name"))
            description = clean_text(row.get("description"))
            major_focus = clean_text(row.get("major_focus"))
            min_gpa = clean_optional_number(row.get("min_gpa"))
            income_ceiling = clean_optional_number(row.get("income_ceiling"))
            state_requirement = clean_text(row.get("state_requirement"))
            combined_text = f"{major_focus} {description}".strip()

            print(f"[{idx}] Processing: {name or 'Unnamed program'}")

            try:
                embedding = get_embedding(client, combined_text)
                if len(embedding) != EMBEDDING_DIM:
                    raise ValueError(
                        f"Embedding length {len(embedding)} does not match {EMBEDDING_DIM}."
                    )
            except Exception as exc:
                skipped_count += 1
                print(f"[{idx}] Skipped due to embedding error: {exc}")
                time.sleep(API_DELAY_SECONDS)
                continue

            record_id = str(uuid.uuid4())

            try:
                insert_financial_opportunity(
                    conn=conn,
                    record_id=record_id,
                    name=name,
                    description=description,
                    min_gpa=min_gpa,
                    income_ceiling=income_ceiling,
                    state_requirement=state_requirement,
                    embedding=embedding,
                )
                conn.commit()
                inserted_count += 1
                print(f"[{idx}] Inserted with id: {record_id}")
            except Exception as exc:
                conn.rollback()
                skipped_count += 1
                print(f"[{idx}] Skipped due to database error: {exc}")

            time.sleep(API_DELAY_SECONDS)

    print(
        f"Done. Attempted: {len(df_subset)}, Inserted: {inserted_count}, Skipped: {skipped_count}"
    )


def get_student_embedding(client,major,extracurriculars):
    text = f"Major: {major} {extracurriculars}".strip()
    return get_embedding(client, text)

def rank_scholarships(conn, embedding, gpa, income, state):
    sql = """
        SELECT id, name, description,
               embedding <=> %s AS distance
        FROM financial_opportunities
        WHERE
            min_gpa IS NOT NULL
            AND min_gpa <= %s
            AND (income_ceiling IS NULL OR income_ceiling >= %s)
            AND (state_requirement = %s OR state_requirement = 'National')
        ORDER BY embedding <=> %s
        LIMIT 10;
    """

    vector_literal = vector_to_pgvector_literal(embedding)

    with conn.cursor() as cursor:
        cursor.execute(sql, (vector_literal, gpa, income, state, vector_literal))
        return cursor.fetchall()


if __name__ == "__main__":
    process_rows()