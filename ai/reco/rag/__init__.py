"""4단계 RAG — 추천 근거 설명(explain) · 규정 · 용어 문답(ask). 실습 U2 marine_rag 를 서비스용으로 줄여 옮겼다.

  corpus.py  문서(서비스 설명 · 특보 · 수칙 · 용어) → 청크 → rag_doc 표
  search.py  BM25(Kiwi 형태소) + TF-IDF(글자 조각) 를 RRF 로 합친 하이브리드 검색
  llm.py     ollama(기본) · openai · claude · mock — 모두 '조각(델타)을 흘려보내는' 같은 모양
  answer.py  프롬프트 · 스트림 이벤트 · 답 검사(인용 · 숫자)

원칙: 숫자는 모델(추천 표)에서, 말은 LLM 에서. LLM 이 숫자를 지어내면 검사에서 잡아 화면에 표시한다.
"""
