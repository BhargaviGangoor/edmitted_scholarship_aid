# EdMitted Scholarship Matcher API

FastAPI service for scholarship matching using structured eligibility filters, vector similarity, and LLM-powered explanation/chat features.

## What This Project Does

1. Ingests scholarships from CSV into PostgreSQL with embeddings.
2. Filters scholarships by hard eligibility rules (GPA, income, state).
3. Scores candidates with:
   - achievement score (vector similarity + text keyword bonus)
   - need score (student income + scholarship income targeting)
4. Ranks all eligible rows, then returns the best matches.
5. Generates a natural-language explanation of top results.
6. Supports transcript parsing and chat-driven profile collection.

## File-by-File Guide

- `app.py`
  - FastAPI entrypoint.
  - Defines endpoints:
    - `GET /`
    - `POST /api/match-scholarships`
    - `POST /api/parse-gradecard`
    - `POST /api/chat`
  - Runs end-to-end matching flow:
    - embed student profile
    - fetch eligible scholarships from DB
    - compute achievement/need percentages
    - apply thresholds
    - rank all valid rows and return top results
  - Calls LLM explanation generation for final matches.

- `database.py`
  - Database/query helpers used by API runtime.
  - Builds student embedding input text.
  - Queries eligible scholarships from `financial_opportunities` with:
    - GPA filter
    - income ceiling filter
    - state filter (`state_requirement` or `National`)
  - Returns vector distance + text rank for downstream scoring.

- `ingest.py`
  - Data ingestion pipeline from CSV to PostgreSQL.
  - Loads `edmitted_top100_scholarships.csv`.
  - Generates embeddings for each scholarship text.
  - Clears and repopulates `financial_opportunities` table.
  - Handles nullable numeric fields and embedding/model fallback.

- `llm_services.py`
  - LLM utility layer.
  - `generate_explanation`: creates concise explanation for top matches.
  - `parse_gradecard`: extracts profile JSON from transcript/gradecard text.
  - `process_chat_message`: runs advisor chat and intercepts trigger JSON when profile is complete.

- `models.py`
  - Pydantic request/response models:
    - `StudentProfile`
    - `GradecardRequest`
    - `ChatMessage`
    - `ChatRequest`

- `scoring.py`
  - Pure scoring helpers:
    - `achievement_percentage(distance)`
    - `need_percentage(student_income, income_ceiling)`

- `requirements.txt`
  - Python dependencies for API, DB, and Gemini integration.

- `edmitted_top100_scholarships.csv`
  - Scholarship source data used during ingestion.

## Prerequisites

- Python 3.10+
- PostgreSQL with `pgvector` enabled
- Google Gemini API key

## Environment Variables

Create a `.env` file in project root:

```env
GEMINI_API_KEY=your_gemini_key
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

## Install

```bash
pip install -r requirements.txt
```

## Ingest Scholarship Data

Run this whenever CSV data changes:

```bash
python ingest.py
```

## Run API

```bash
python -m uvicorn app:app --reload --port 8001
```

Open docs:

```text
http://127.0.0.1:8001/docs
```

## API Endpoints

### `GET /`

Basic health response.

### `POST /api/match-scholarships`

Input example:

```json
{
  "gpa": 3.8,
  "income": 65000,
  "state": "California",
  "major": "Computer Science",
  "extracurriculars": "Robotics club"
}
```

Response includes:

- `achievement_table` (top 10 by achievement)
- `need_table` (top 10 by need)
- `final_matches` (best overall matches from full eligible set)
- `explanation`

### `POST /api/parse-gradecard`

Parses free-text gradecard/transcript into student profile fields.

### `POST /api/chat`

Chat endpoint that collects required profile details and automatically triggers scholarship matching once all required fields are present.

## Notes

- Final ranking evaluates all valid eligible rows before selecting top output matches.
- If your CSV contains `No Limit` for income, the ingestion parser currently treats non-numeric values as null.
