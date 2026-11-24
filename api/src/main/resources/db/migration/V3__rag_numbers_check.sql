-- 4단계: 답 검사에 '숫자 검사'를 더한다 — 답에 나온 숫자가 모두 근거(추천 표 · 문서)에 있었나
ALTER TABLE rag_qa_log ADD COLUMN numbers_ok BOOLEAN NULL AFTER made_up;
ALTER TABLE rag_qa_log ADD COLUMN species VARCHAR(10) NULL AFTER mode;
ALTER TABLE rag_qa_log ADD COLUMN rec_date DATE NULL AFTER species;
