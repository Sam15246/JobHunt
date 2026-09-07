CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ENUMs
CREATE TYPE job_source AS ENUM (
    'naukri', 'linkedin', 'greenhouse', 'lever', 'career_page'
);

CREATE TYPE geo_region AS ENUM (
    'india', 'singapore', 'uk', 'saudi_arabia',
    'new_zealand', 'australia', 'netherlands', 'remote', 'other'
);

CREATE TYPE ats_type AS ENUM (
    'naukri', 'greenhouse', 'lever', 'workday', 'unknown'
);

CREATE TYPE job_status AS ENUM (
    'scraped', 'keyword_passed', 'keyword_failed',
    'scored', 'scored_low',
    'resume_assigned', 'ready_to_apply', 'ready_for_manual_apply',
    'submitted', 'failed', 'skipped'
);

CREATE TYPE resume_variant AS ENUM ('backend', 'qa');

CREATE TYPE application_status AS ENUM (
    'submitted', 'failed', 'interview', 'rejected', 'offer'
);

-- Tables
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,
    source job_source NOT NULL,
    jd_text TEXT,
    location TEXT,
    geo_region geo_region,
    requires_sponsorship BOOLEAN,
    ats_type ats_type NOT NULL DEFAULT 'unknown',
    status job_status NOT NULL DEFAULT 'scraped',
    keyword_score INT,
    claude_score INT,
    claude_reason TEXT,
    resume_variant resume_variant,
    discovered_sources TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    status application_status NOT NULL,
    resume_path TEXT,
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    error_log TEXT,
    screenshot_path TEXT
);

-- Indexes
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_ats_type ON jobs(ats_type);
CREATE INDEX idx_jobs_source ON jobs(source);
CREATE INDEX idx_applications_job_id ON applications(job_id);
CREATE INDEX idx_applications_status ON applications(status);
