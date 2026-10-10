# LearnMate AI — Source-Grounded Multimodal Study Companion
> **Multimodal AI Hackathon 2026 • Track D: Personalized Tutoring & Adaptive Learning**

LearnMate AI is a production-grade, source-grounded educational companion that ingests multimodal course materials (textbooks, slide decks, lecture recordings); creates a strictly verified knowledge base; answers inquiries with clickable exact source citations; generates adaptive assessments; diagnoses cognitive misconceptions; and personalizes tutoring using **deterministic Bayesian Knowledge Tracing (BKT)**.

---

## 🌟 Key Capabilities

### 1. Multimodal Document & Lecture Ingestion
- **PDF Extraction**: Page-by-page text, table parsing (`find_tables`), and diagram extraction via **PyMuPDF**. Diagrams and figures are analyzed using Gemini multimodal vision models so visual concepts become grounded, searchable knowledge units.
- **PowerPoint Ingestion**: Slide-by-slide titles, body hierarchies, speaker notes, and embedded tables extracted via **python-pptx**, preserving 1-indexed `slide_number`.
- **Lecture Video & Audio Processing**: Extracts timestamped lecture transcript segments with start and end timecodes (`[03:15 - 06:40]`). Supports Gemini multimodal audio/video understanding and sidecar transcript formats.
- **Source-Aware Chunking**: Guarantees that every chunk retains exact file provenance, page number, slide number, or video timestamp range.

### 2. Strictly Grounded AI Tutor
- **Hybrid Retrieval**: Combines BM25 keyword matching with dense 768-dimensional semantic embeddings using **Reciprocal Rank Fusion (RRF)**.
- **Zero Hallucination Attribution**: Answers are strictly backed by retrieved source passages with clickable citations.
- **Negative Rejection for Unsupported Queries**: If a question falls outside the uploaded course materials (e.g. baking croissants, quantum cryptography), the tutor explicitly rejects the query rather than inventing references.
- **Separation of External Knowledge**: External supplementary study context is cleanly separated from course-grounded claims.

### 3. Adaptive Assessments & Misconception Diagnosis
- **Multi-Format Generation**: Generates MCQs, short-answer questions, and numerical problems dynamically tailored by topic, difficulty tier, and question count.
- **Citation-Backed Answer Keys**: Every question is grounded in a specific source excerpt.
- **Cognitive Misconception Analysis**: When a student answers incorrectly, LearnMate AI diagnoses the underlying cognitive misconception, generates targeted remediation advice, and recommends specific reading citations.

### 4. Deterministic Bayesian Knowledge Tracing (BKT)
- **Mathematical Formulation**:
  $$P(L_t \mid \text{Correct}) = \frac{P(L_{t-1}) \cdot (1 - S)}{P(L_{t-1}) \cdot (1 - S) + (1 - P(L_{t-1})) \cdot G}$$
  $$P(L_t \mid \text{Incorrect}) = \frac{P(L_{t-1}) \cdot S}{P(L_{t-1}) \cdot S + (1 - P(L_{t-1})) \cdot (1 - G)}$$
  $$P(L_{t+1}) = P(L_t \mid \text{Obs}) + (1 - P(L_t \mid \text{Obs})) \cdot T$$
- Updates topic mastery deterministically upon quiz attempts.
- Recommends diagnostic reviews and prerequisite revisions when mastery falls below target.

### 5. Reproducible RAG Evaluation Suite
- **Benchmarked Across 4 Categories**: Grounded Factual, Multi-Source Synthesis, Diagram/Vision Questions, and Unsupported Adversarial Questions.
- **Real Measured Metrics**: Measures Faithfulness, Answer Relevancy, Context Precision, Context Recall, Question Repetition Rate, and Unsupported Rejection Rate.
- **Multi-Session Learner Simulation**: Evaluates beginner, intermediate, and advanced student personas across progressive learning sessions.

---

## 🛠️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | Next.js 16 (App Router), TypeScript, Tailwind CSS, Lucide Icons |
| **Backend** | Python 3.12, FastAPI, Pydantic v2, Uvicorn |
| **AI Models** | Google Gemini 2.0 Flash (`google-genai`), `text-embedding-004` |
| **Document Processing** | PyMuPDF (`fitz`), `python-pptx`, Gemini Multimodal Vision/Audio |
| **Database** | Supabase PostgreSQL + `pgvector` / Local Embedded SQLite + Numpy Vector Engine |
| **Retrieval** | BM25 (`rank-bm25`) + Dense Cosine Similarity + Reciprocal Rank Fusion |
| **Evaluation** | Automated RAG benchmark runner + Bayesian simulated student agent sessions |

---

## 📁 Repository Structure

```
multimodal hackathon/
├── backend/
│   ├── app/
│   │   ├── core/               # Configuration & Google GenAI client
│   │   │   ├── config.py
│   │   │   └── gemini.py
│   │   ├── db/                 # Dual storage engine (Supabase or Local)
│   │   │   └── storage.py
│   │   ├── models/             # Pydantic schemas
│   │   │   └── schema.py
│   │   ├── services/
│   │   │   ├── ingestion/      # PDF, PPTX, Video/Audio multimodal parsers
│   │   │   │   ├── base.py
│   │   │   │   ├── pdf_parser.py
│   │   │   │   ├── pptx_parser.py
│   │   │   │   └── video_parser.py
│   │   │   ├── retrieval/      # Hybrid BM25 + Vector retriever
│   │   │   │   └── hybrid_retriever.py
│   │   │   ├── tutor/          # Grounded AI tutor with negative rejection
│   │   │   │   └── grounded_tutor.py
│   │   │   ├── assessment/     # Adaptive quiz generator & misconception diagnosis
│   │   │   │   └── generator.py
│   │   │   ├── learner/        # Deterministic BKT mastery model
│   │   │   │   └── mastery_model.py
│   │   │   └── evaluation/     # Benchmark pipeline & learner simulation
│   │   │       └── benchmark.py
│   │   ├── routers/            # FastAPI API endpoints
│   │   │   ├── health.py
│   │   │   ├── courses.py
│   │   │   ├── ingestion.py
│   │   │   ├── tutor.py
│   │   │   ├── assessment.py
│   │   │   ├── learner.py
│   │   │   └── evaluation.py
│   │   └── main.py             # FastAPI application & startup seeder
│   ├── db/
│   │   └── schema.sql          # Supabase PostgreSQL + pgvector schema
│   ├── tests/                  # Automated test suite (9 passing tests)
│   │   └── test_backend.py
│   ├── run.py                  # Backend launcher
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx      # App shell with Sidebar & Header
│   │   │   ├── page.tsx        # Dashboard
│   │   │   ├── courses/        # Course Ingestion & document status
│   │   │   ├── tutor/          # Grounded AI Tutor chat & citations
│   │   │   ├── assessments/    # Adaptive quiz runner & misconception reports
│   │   │   ├── progress/       # Topic-level BKT analytics
│   │   │   └── evaluation/     # Live RAG benchmark visualizer
│   │   ├── components/         # Reusable UI components
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   ├── CitationCard.tsx
│   │   │   ├── MasteryBar.tsx
│   │   │   └── SourceViewerModal.tsx
│   │   └── lib/                # API client & TypeScript interfaces
│   │       ├── api.ts
│   │       └── types.ts
│   └── package.json
└── README.md
```

---

## 🚀 Getting Started

### 1. Prerequisites
- **Node.js**: v18+ or v20+
- **Python**: 3.10+ or 3.12+

### 2. Backend Setup

```bash
# Navigate to backend and create virtual environment
cd backend
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Copy .env.example to .env and configure GEMINI_API_KEY / SUPABASE credentials
cp .env.example .env

# Run automated tests
pytest tests/test_backend.py -v

# Start backend dev server
python run.py
```
Backend will start on **`http://localhost:8000`** (API documentation at **`http://localhost:8000/docs`**).

### 3. Frontend Setup

```bash
cd frontend

# Install npm dependencies
npm install

# Start Next.js development server
npm run dev
```
Frontend will be live at **`http://localhost:3000`**.

---

## 🗄️ Database Setup (Supabase / Local)

1. **Zero-Config Local Mode (Default)**:
   - When `SUPABASE_URL` is omitted, LearnMate AI automatically activates the embedded storage engine (`backend/data/learnmate.db`) with normalized numpy vector cosine similarity. No cloud accounts, credit cards, or Docker containers are required.
2. **Supabase PostgreSQL + pgvector**:
   - Create a project at [supabase.com](https://supabase.com/).
   - Open the Supabase **SQL Editor** and run the contents of [`backend/db/schema.sql`](backend/db/schema.sql).
   - Set `SUPABASE_URL` and `SUPABASE_KEY` in `backend/.env`.

---

## 🧪 Automated Test Suite

Run the verified test suite covering all critical services:
```bash
pytest backend/tests/test_backend.py -v
```
**Test Coverage**:
- `test_health_endpoint`: System status and engine readiness.
- `test_courses_list_and_seeded_data`: Course repository and seeded multimodal demo documents.
- `test_hybrid_retrieval_and_citation_formatting`: BM25 + dense vector ranking and citation formatting.
- `test_grounded_tutor_answers_supported_query`: Strict answer grounding and citation preservation.
- `test_grounded_tutor_rejects_unsupported_query`: Negative rejection on off-topic questions without hallucination.
- `test_bayesian_knowledge_tracing_deterministic_math`: Monotonic BKT belief updates given correct and incorrect evidence.
- `test_learner_profile_endpoint`: Topic breakdown and adaptive study recommendations.
- `test_assessment_generation_and_grading`: Multi-format quiz generation and citation-backed grading.
- `test_evaluation_run`: Benchmark execution across 4 categories and simulated student sessions.

---

## 🏆 Hackathon Alignment

| Requirement | Implementation in LearnMate AI |
| :--- | :--- |
| **Track D Alignment** | Personalized Tutoring & Adaptive Learning using Bayesian Knowledge Tracing |
| **Multimodal Ingestion** | PDF (PyMuPDF), PPTX (python-pptx), MP4 video transcripts (Gemini Vision/Audio) |
| **Source Grounding** | Exact page numbers, slide indices, video timestamps, and clickable excerpts |
| **Unsupported Rejection** | Rejects off-topic queries with explicit academic notifications |
| **Misconception Diagnosis** | Evaluates student errors, identifies cognitive flaws, and links remediation passages |
| **Reproducible Evaluation** | Real benchmarks measuring Faithfulness, Relevancy, Precision, Recall, and student simulations |
