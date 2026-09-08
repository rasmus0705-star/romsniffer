-- ═══════════════════════════════════════════════
--  Auning Byvandring — Supabase Tables
--  Kør dette i Supabase SQL Editor
-- ═══════════════════════════════════════════════

-- Tabel til individuelle svar
CREATE TABLE answers (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event_id TEXT NOT NULL,
  team_id TEXT NOT NULL,
  team_name TEXT,
  location_id INT NOT NULL,
  question_index INT NOT NULL,
  selected_option INT NOT NULL,
  is_correct BOOLEAN NOT NULL DEFAULT false,
  answered_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Tabel til holdenes færdiggørelse
CREATE TABLE completions (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event_id TEXT NOT NULL,
  team_id TEXT NOT NULL,
  team_name TEXT,
  total_correct INT NOT NULL,
  total_questions INT NOT NULL,
  completed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for hurtig filtrering
CREATE INDEX idx_answers_event ON answers(event_id);
CREATE INDEX idx_answers_team ON answers(event_id, team_id);
CREATE INDEX idx_completions_event ON completions(event_id);

-- Row Level Security — tillad anonym insert og select
ALTER TABLE answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE completions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Alle kan indsætte svar" ON answers
  FOR INSERT WITH CHECK (true);

CREATE POLICY "Alle kan læse svar" ON answers
  FOR SELECT USING (true);

CREATE POLICY "Alle kan indsætte completions" ON completions
  FOR INSERT WITH CHECK (true);

CREATE POLICY "Alle kan læse completions" ON completions
  FOR SELECT USING (true);