"""어장 위치 추천 — 공통 설정. 값은 모두 환경 변수(.env)로 바꿀 수 있다. 키 · 비밀번호는 여기에 적지 않는다."""
import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")   # 저장소 맨 위 .env (web · api 와 같은 파일)
    load_dotenv()                                                # ai/.env 가 있으면 덮어쓰지 않고 보탬
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent                    # ai/
SAMPLE = ROOT / "sample_data"
DATA = Path(os.getenv("DATA_DIR", ROOT / "data"))
MODELS = Path(os.getenv("MODELS_DIR", ROOT / "models" / "registry"))
OUT = Path(os.getenv("OUT_DIR", ROOT / "out"))

TZ = ZoneInfo("Asia/Seoul")
SPECIES = ["고등어", "방어", "삼치"]          # 회유성 — 수온에 따라 어장이 옮겨 다닌다
AUCTION_DAY_CSV = SAMPLE / "auction_day_20261012.csv"
AUCTION_DAILY_CSV = Path(os.getenv("AUCTION_DAILY_CSV", SAMPLE / "auction_daily_2025_2026.csv"))
FISHING_INDEX_CSV = SAMPLE / "fishing_index_20261014.csv"
MARKETS_CSV = SAMPLE / "markets.csv"
INDEX_ORDER = ["매우나쁨", "나쁨", "보통", "좋음", "매우좋음"]

# 자료를 어디서 읽나: db (서비스 · 기본) | csv (실습 · 테스트)
DATA_SOURCE = os.getenv("DATA_SOURCE", "db")

# 시연(demo): 고정된 '오늘' — 비워 두면 실제 오늘(서울 시간)
DEMO_TODAY = os.getenv("DEMO_TODAY", "").strip()

# 서버끼리 쓰는 내부 토큰 (Spring → FastAPI)
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "")

# ── 라벨 확정 · 재학습 · 자동 교체 기준 (PRD 6절) ─────────────────────────────
LABEL_MATURE_DAYS = int(os.getenv("LABEL_MATURE_DAYS", "7"))      # D 의 라벨은 D+7 에 확정
EVAL_WEEKS = int(os.getenv("EVAL_WEEKS", "8"))                     # 평가 창 = 확정된 날 중 최근 8주
PROMO_MIN_DIFF = float(os.getenv("PROMO_MIN_DIFF", "0.01"))        # 후보 − 챔피언 P@3 ≥ 0.01
PROMO_MIN_DAYS = int(os.getenv("PROMO_MIN_DAYS", "30"))            # 품목별 확정 평가일 ≥ 30
PROMO_MAX_SPECIES_DROP = float(os.getenv("PROMO_MAX_SPECIES_DROP", "0.03"))
COLLECT_MIN_SUCCESS = float(os.getenv("COLLECT_MIN_SUCCESS", "0.95"))
BOOTSTRAP_N = int(os.getenv("BOOTSTRAP_N", "1000"))
WIND_WARN = float(os.getenv("WIND_WARN", "14"))                     # m/s — 이 이상이면 경고 (순위는 그대로)


def now() -> datetime:
    return datetime.now(TZ)


def today() -> date:
    """서비스의 '오늘'. DEMO_TODAY=2026-10-15 처럼 두면 캡처 · 수업에서 늘 같은 화면이 나온다."""
    return date.fromisoformat(DEMO_TODAY) if DEMO_TODAY else now().date()
