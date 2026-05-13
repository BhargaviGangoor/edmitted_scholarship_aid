# EdMitted Scholarship Matcher API

A high-performance scholarship matching engine built with **FastAPI**, **PostgreSQL (pgvector)**, and **Google Gemini**.

## 🚀 Overview

EdMitted helps students find the best scholarship opportunities by combining:
- **Vector Similarity Search**: Matches student interests and extracurriculars using LLM embeddings.
- **Structured Eligibility Filters**: Enforces hard rules like GPA, income ceilings, and state residency.
- **LLM-Powered Insights**: Generates natural language explanations for why a scholarship is a good fit.
- **Intelligent Chat Advisor**: A conversational interface that collects student profiles and provides instant matches.

---

## 📂 Project Structure

```text
edmitted/
├── data/               # Scholarship source data (CSV)
├── scripts/            # Database setup and data ingestion tools
├── src/
│   ├── api/           # FastAPI application and routes
│   ├── core/          # Database connection, scoring logic, and config
│   ├── models/        # Pydantic data schemas
│   └── services/      # LLM integration logic
├── .env.example       # Template for environment variables
├── requirements.txt   # Project dependencies
└── README.md          # Documentation
```

---

## 🛠️ Tech Stack

- **Backend**: Python 3.10+, FastAPI
- **Database**: PostgreSQL with `pgvector` extension
- **AI/ML**: Google Gemini (Flash & Pro models), Gemini Embeddings
- **Data Processing**: Pandas, Psycopg2

---

## ⚙️ Setup Instructions

### 1. Prerequisites
- Python 3.10 or higher
- PostgreSQL with the `pgvector` extension enabled
- Google Gemini API Key ([Get one here](https://aistudio.google.com/))

### 2. Installation
Clone the repository and install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the root directory (use `.env.example` as a template):
```env
GEMINI_API_KEY=your_gemini_key
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
```

### 4. Database Initialization
Initialize the database schema and pgvector extension:
```bash
python -m scripts.setup_local_db
```

### 5. Data Ingestion
Load the scholarship data from CSV into your database:
```bash
python -m scripts.ingest
```

---

## 🚦 Running the Application

Start the FastAPI server:
```bash
python -m uvicorn src.api.main:app --reload --port 8001
```

Access the interactive API documentation:
- **Swagger UI**: [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)

---

## 🔌 API Endpoints

### `POST /api/match-scholarships`
Matches a student profile against the scholarship database.
- **Input**: GPA, Income, State, Major, Extracurriculars.
- **Output**: Ranked matches, achievement/need scores, and an AI-generated explanation.

### `POST /api/parse-gradecard`
Parses transcript text into a structured student profile.

### `POST /api/chat`
A conversational AI agent that collects profile details and triggers matching automatically.

---

## 🧪 Test Cases

Use these JSON payloads to test the API endpoints via Swagger UI or Postman.

### 1. Scholarship Matching (`POST /api/match-scholarships`)

| Scenario | Payload |
| :--- | :--- |
| **Tech Student** | `{"gpa": 3.9, "income": 40000, "state": "National", "major": "Computer Science", "extracurriculars": "AI projects machine learning hackathons"}` |
| **Medical Student** | `{"gpa": 3.8, "income": 30000, "state": "National", "major": "Medicine", "extracurriculars": "hospital volunteering clinical research"}` |
| **Arts Student** | `{"gpa": 3.6, "income": 45000, "state": "National", "major": "Fine Arts", "extracurriculars": "painting exhibitions digital art"}` |
| **High Income** | `{"gpa": 3.8, "income": 200000, "state": "National", "major": "Computer Science", "extracurriculars": "AI research internships"}` |
| **Low GPA Filter** | `{"gpa": 2.5, "income": 40000, "state": "National", "major": "Computer Science", "extracurriculars": "coding projects"}` |
| **Mixed Domain** | `{"gpa": 3.7, "income": 50000, "state": "National", "major": "Computer Science", "extracurriculars": "painting exhibitions digital art"}` |
| **Business** | `{"gpa": 3.7, "income": 50000, "state": "National", "major": "Business Administration", "extracurriculars": "startup founder marketing"}` |
| **State Filter** | `{"gpa": 3.8, "income": 40000, "state": "California", "major": "Computer Science", "extracurriculars": "AI projects hackathons"}` |
| **Empty Text** | `{"gpa": 3.5, "income": 50000, "state": "National", "major": "", "extracurriculars": ""}` |
| **Perfect Match** | `{"gpa": 4.0, "income": 20000, "state": "National", "major": "Computer Science", "extracurriculars": "AI research internships hackathons"}` |

### 2. Gradecard Parsing (`POST /api/parse-gradecard`)

```json
{
  "gradecard_text": "Name: Sarah\nGPA: 3.8\nIncome: 40000\nState: California\nSubjects: Computer Science, Math\nActivities: Hackathons, AI club"
}
```

### 3. AI Chat Advisor (`POST /api/chat`)

**Scenario A: Profile Collection**
```json
{
  "messages": [
    {"role": "user", "content": "My GPA is 3.8"},
    {"role": "user", "content": "Income is 35000"},
    {"role": "user", "content": "I live in California"},
    {"role": "user", "content": "I study Computer Science"},
    {"role": "user", "content": "I do AI projects and hackathons"}
  ]
}
```

**Scenario B: Conversational Flow**
```json
{
  "messages": [
    {"role": "user", "content": "Hey"},
    {"role": "model", "content": "Hi! What's your GPA?"},
    {"role": "user", "content": "3.6"},
    {"role": "model", "content": "What’s your income?"},
    {"role": "user", "content": "30000"},
    {"role": "model", "content": "State?"},
    {"role": "user", "content": "Texas"},
    {"role": "model", "content": "Major?"},
    {"role": "user", "content": "Computer Science"},
    {"role": "model", "content": "Activities?"},
    {"role": "user", "content": "Hackathons"}
  ]
}
```

---

## 🧠 Match Logic

1. **Filtering**: Excludes scholarships where the student doesn't meet GPA or state requirements.
2. **Scoring**:
   - **Achievement Match**: Vector distance (LLM) + Keyword matching bonus.
   - **Need Match**: Calculated based on family income relative to scholarship ceilings.
3. **Ranking**: Weighted combination of Achievement (60%) and Need (40%).
4. **Explanation**: RAG-based generation using top matches to provide context to the student.

---

## 📝 License
This project is for educational purposes. All scholarship data is sourced from EdMitted.
