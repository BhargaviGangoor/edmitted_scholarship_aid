# 🎓 EdMitted Scholarship & Financial Aid Match Engine

A **FastAPI-based microservice** that intelligently matches students with the most suitable scholarships and financial aid opportunities using a **dual-probability scoring system**.

---

## 🚀 Features

* 🎯 **Achievement Match (%)**

  * Based on GPA, SAT score, and extracurriculars
  * Uses percentile-style comparison for realistic evaluation

* 💰 **Need Match (%)**

  * Based on family income and affordability
  * Uses net price vs sticker price analysis

* ⚖️ **Weighted Scoring System**

  * Customizable importance between merit and financial need
  * Dynamic ranking based on user preference

* 🏆 **Top 10 Recommendations**

  * Returns the most relevant programs sorted by overall match

* ⚡ **FastAPI Microservice**

  * Lightweight, scalable, and easy to integrate with other systems

---

## 🛠️ Tech Stack

* **Backend:** FastAPI
* **Language:** Python
* **Data Processing:** Pandas
* **Server:** Uvicorn

---

## 📡 API Endpoints

### 1. POST `/match-scholarships`

Generates top 10 scholarship matches.

#### 📥 Sample Input

```json
{
  "gpa": 3.8,
  "sat": 1400,
  "extracurriculars": ["DECA President", "Volunteer"],
  "family_income": 50000,
  "achievement_weight": 0.6,
  "need_weight": 0.4
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

* Compares student GPA against simulated institutional percentiles
* Adjusted using SAT score and extracurricular involvement
* Produces a normalized score (0–98%)

### 🔹 Need Match

* Maps income to financial aid brackets (NPT columns)
* Evaluates affordability using net price vs total cost
* Generates a financial compatibility score

### 🔹 Final Ranking

```
Overall Score = (Achievement × Weight) + (Need × Weight)
```

* Results are sorted by overall score
* Top 10 programs are returned

---

## 📂 Dataset

⚠️ The dataset is **not included** in this repository due to GitHub size limits.

### Required:

* `Most-Recent-Cohorts-All-Data-Elements.csv`

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

* Scores are capped below 100% to maintain realistic variation
* Randomized elements simulate institutional diversity where data is missing
* Designed to integrate with a Node.js backend as a scoring engine

---

## 💡 Future Improvements

* Integrate real GPA percentile datasets
* Add filtering for program types (STEM, Business, etc.)
* Improve explainability using AI-generated summaries

---

.
