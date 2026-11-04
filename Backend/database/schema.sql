
CREATE TABLE IF NOT EXISTS candidates (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    education TEXT,
    skills TEXT,
    experience TEXT,
    bio TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_candidate_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS assessments (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    difficulty VARCHAR(20) NOT NULL
        CHECK (difficulty IN ('easy', 'medium', 'hard')),
    duration INTEGER NOT NULL
        CHECK (duration > 0),
    created_by INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_assessment_employer
        FOREIGN KEY (created_by)
        REFERENCES users(id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS submissions (
    id SERIAL PRIMARY KEY,
    candidate_id INTEGER NOT NULL,
    assessment_id INTEGER NOT NULL,
    answers JSONB DEFAULT '{}'::jsonb,
    score NUMERIC(5,2),
    status VARCHAR(20) NOT NULL DEFAULT 'in_progress'
        CHECK (status IN ('in_progress', 'submitted', 'evaluated')),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    submitted_at TIMESTAMP,

    CONSTRAINT fk_submission_candidate
        FOREIGN KEY (candidate_id)
        REFERENCES candidates(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_submission_assessment
        FOREIGN KEY (assessment_id)
        REFERENCES assessments(id)
        ON DELETE RESTRICT,

    CONSTRAINT unique_candidate_assessment
        UNIQUE (candidate_id, assessment_id),

    CONSTRAINT chk_submission_score
        CHECK (score IS NULL OR (score >= 0 AND score <= 100))
);

CREATE INDEX IF NOT EXISTS idx_assessments_created_by
    ON assessments(created_by);

CREATE INDEX IF NOT EXISTS idx_submissions_candidate
    ON submissions(candidate_id);

CREATE INDEX IF NOT EXISTS idx_submissions_assessment
    ON submissions(assessment_id);
