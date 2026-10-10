-- ============================================================================
-- LearnMate AI - Database Schema (Supabase PostgreSQL + pgvector)
-- Multimodal AI Hackathon 2026: Track D (Personalized Tutoring & Adaptive Learning)
-- ============================================================================

-- Enable vector extension for dense semantic embeddings
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. COURSES
CREATE TABLE IF NOT EXISTS courses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. DOCUMENTS (Ingested PDF, PPT/PPTX, MP4)
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL CHECK (file_type IN ('pdf', 'pptx', 'ppt', 'mp4', 'audio')),
    file_path TEXT NOT NULL,
    ingestion_status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (ingestion_status IN ('pending', 'processing', 'completed', 'failed')),
    error_message TEXT,
    total_pages_or_slides INTEGER,
    duration_seconds REAL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. DOCUMENT CHUNKS (Source-grounded content units)
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    chunk_type VARCHAR(50) NOT NULL DEFAULT 'text' CHECK (chunk_type IN ('text', 'table', 'diagram', 'transcript')),
    source_type VARCHAR(50) NOT NULL CHECK (source_type IN ('pdf', 'pptx', 'ppt', 'mp4', 'audio')),
    page_number INTEGER,
    slide_number INTEGER,
    start_timestamp VARCHAR(50),
    end_timestamp VARCHAR(50),
    topic VARCHAR(255),
    concept VARCHAR(255),
    embedding vector(768),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create HNSW vector index for cosine distance search
CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx 
ON document_chunks USING hnsw (embedding vector_cosine_ops);

-- Create Full-Text Search index for hybrid keyword retrieval
CREATE INDEX IF NOT EXISTS document_chunks_content_fts_idx 
ON document_chunks USING gin (to_tsvector('english', content));

-- 4. TOPICS & CONCEPTS (Curriculum Knowledge Graph)
CREATE TABLE IF NOT EXISTS topics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    prerequisites JSONB DEFAULT '[]'::jsonb, -- Array of prerequisite topic IDs / names
    order_index INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. LEARNER PROFILES
CREATE TABLE IF NOT EXISTS learner_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    overall_mastery REAL DEFAULT 0.0 CHECK (overall_mastery >= 0.0 AND overall_mastery <= 1.0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. TOPIC MASTERY (Bayesian Knowledge Tracing / Mastery State)
CREATE TABLE IF NOT EXISTS topic_mastery (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    topic_name VARCHAR(255) NOT NULL,
    mastery_score REAL DEFAULT 0.1 CHECK (mastery_score >= 0.0 AND mastery_score <= 1.0),
    p_transit REAL DEFAULT 0.15, -- BKT learning transition probability
    p_guess REAL DEFAULT 0.20,   -- BKT guess probability
    p_slip REAL DEFAULT 0.10,    -- BKT slip probability
    attempts_count INTEGER DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT topic_mastery_user_topic_uniq UNIQUE (user_id, topic_name)
);

-- 7. ASSESSMENTS
CREATE TABLE IF NOT EXISTS assessments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID REFERENCES courses(id) ON DELETE SET NULL,
    user_id VARCHAR(255) NOT NULL,
    title VARCHAR(255) NOT NULL,
    assessment_type VARCHAR(50) NOT NULL CHECK (assessment_type IN ('diagnostic', 'adaptive_quiz', 'practice')),
    difficulty VARCHAR(50) NOT NULL CHECK (difficulty IN ('beginner', 'intermediate', 'advanced', 'adaptive')),
    total_questions INTEGER NOT NULL,
    score REAL,
    status VARCHAR(50) NOT NULL DEFAULT 'generated' CHECK (status IN ('generated', 'in_progress', 'completed')),
    misconception_analysis JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 8. ASSESSMENT QUESTIONS
CREATE TABLE IF NOT EXISTS assessment_questions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id UUID REFERENCES assessments(id) ON DELETE CASCADE,
    topic_name VARCHAR(255) NOT NULL,
    question_type VARCHAR(50) NOT NULL CHECK (question_type IN ('mcq', 'short_answer', 'numerical')),
    prompt TEXT NOT NULL,
    options JSONB, -- Array of strings for MCQ
    correct_answer TEXT NOT NULL,
    explanation TEXT NOT NULL,
    citation JSONB NOT NULL, -- {source_file, page_number, slide_number, timestamp, excerpt}
    student_answer TEXT,
    is_correct BOOLEAN,
    feedback TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 9. EVALUATION RUNS
CREATE TABLE IF NOT EXISTS evaluation_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    run_name VARCHAR(255) NOT NULL,
    dataset_type VARCHAR(100) NOT NULL,
    faithfulness REAL NOT NULL,
    answer_relevancy REAL NOT NULL,
    context_precision REAL NOT NULL,
    context_recall REAL NOT NULL,
    question_repetition_rate REAL NOT NULL,
    simulation_results JSONB DEFAULT '{}'::jsonb,
    detailed_metrics JSONB DEFAULT '{}'::jsonb
);
