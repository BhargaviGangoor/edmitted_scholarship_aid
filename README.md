# 🎓 EdMitted Financial Aid & Scholarship Matcher

A **FastAPI-based microservice** that intelligently matches students with the most suitable scholarships and financial aid opportunities using a **hybrid retrieval engine** (SQL filtering + pgvector semantic search).

---

## 🚀 Features

- 🎯 **Two-Stage Search Algorithm**
  - **Stage 1 (Hard SQL Filtering):** Immediately excludes disqualifying scholarships based on strict, non-negotiable parameters (GPA limits, Income Ceilings, State of Residence).
  - **Stage 2 (Semantic Ranking):** Uses Google Gemini embeddings and PostgreSQL `pgvector` to rank valid scholarships based on the semantic similarity of the student's major and extracurriculars to the scholarship's open-text description.

- ⚖️ **Match Scoring System**
  - **Achievement Match (%):** Evaluates semantic alignment using vector Cosine Distance.
  - **Need Match (%):** Generates a standardized score based on financial need brackets and Adjusted Gross Income (AGI).
  - **Overall Match (%):** A calculated weighted combination prioritizing achievement (70%) and need (30%).

- ⚡ **FastAPI Microservice**
  - Lightweight, scalable API returning the top 10 best-matched programs in milliseconds.

---

## 🛠️ Tech Stack

- **Backend:** FastAPI, Python
- **Database:** PostgreSQL (with `pgvector` extension)
- **AI / Embeddings:** Google Gemini API
- **Data Processing:** Pandas, psycopg2

---

## 📡 API Endpoints

### POST `/api/match-scholarships`

Generates the top 10 scholarship matches based on a student's profile.

#### 📥 Sample Input

```json
{
  "gpa": 3.8,
  "income": 50000.0,
  "state": "WA",
  "major": "Computer Science",
  "extracurriculars": "Debate club president, volunteer math tutor"
}
```

#### 📤 Sample Output

```json
[
  {
    "rank": 1,
    "program": "University X / Institutional Grant",
    "achievement_match": "94.2%",
    "achievement_label": "Very High",
    "need_match": "88.7%",
    "need_label": "High",
    "logic_summary": "Strong academic performance with strong affordability"
  }
]
```

---

### 2. GET `/health`

Health check endpoint.

#### Response

```json
{
  "status": "ok"
}
```

---

## 🧠 How It Works

### 🔹 Achievement Match

- Compares student GPA against simulated institutional percentiles
- Adjusted using SAT score and extracurricular involvement
- Produces a normalized score (0–98%)

### 🔹 Need Match

- Maps income to financial aid brackets (NPT columns)
- Evaluates affordability using net price vs total cost
- Generates a financial compatibility score

### 🔹 Final Ranking

```
Overall Score = (Achievement × Weight) + (Need × Weight)
```

- Results are sorted by overall score
- Top 10 programs are returned

---

## 📂 Dataset

⚠️ The dataset is **not included** in this repository due to GitHub size limits.

### Required:

- `Most-Recent-Cohorts-All-Data-Elements.csv`

👉 Place the dataset in the root directory before running the project.

---

## ▶️ Running the Project

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Start server

```bash
python -m uvicorn main:app --port 8001
```

### 3. Open Swagger UI

```
http://127.0.0.1:8001/docs
```

---

## 📌 Notes

- Scores are capped below 100% to maintain realistic variation
- Randomized elements simulate institutional diversity where data is missing
- Designed to integrate with a Node.js backend as a scoring engine

---

## 💡 Future Improvements

- Integrate real GPA percentile datasets
- Add filtering for program types (STEM, Business, etc.)
- Improve explainability using AI-generated summaries

---

.
