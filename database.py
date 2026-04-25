import psycopg2

def vector_to_pgvector_literal(vector: list[float]) -> str:
    """Convert a Python list of floats into a string like '[0.1, 0.2, ...]'."""
    return "[" + ",".join(str(x) for x in vector) + "]"

def get_embedding(client, text: str) -> list[float]:
    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text
    )
    return response.embeddings[0].values

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
