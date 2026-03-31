# ArtMap — DB 구축 가이드

미술관·작가·작품 데이터를 수집해 PostgreSQL DB를 구성하는 프로젝트입니다.

---

## 사전 준비

| 도구 | 버전 |
|------|------|
| Python | 3.11+ |
| Docker & Docker Compose | 최신 버전 |

---

## 1. 초기 설정

### 1-1. 저장소 클론

```bash
git clone <repository-url>
cd artmap
```

### 1-2. 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일의 기본값은 그대로 사용해도 됩니다.

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=artmap
DB_USER=postgres
DB_PASSWORD=artmap123
```

### 1-3. Python 가상 환경 생성 및 패키지 설치

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 2. DB 실행 및 테이블 생성

### 2-1. PostgreSQL 컨테이너 시작

```bash
make docker-up
```

### 2-2. 테이블 생성

```bash
python3 init_db.py
```

> 테이블을 초기화(전체 삭제 후 재생성)하려면: `python3 init_db.py --drop` 후 `python3 init_db.py`
> 또는 `make db-reset`

---

## 3. 데이터 수집

### 전체 수집 (권장)

미술관 → 작가 → 작품 순서로 한 번에 수집합니다.

```bash
python3 scripts/ingest_all.py
```

수집 결과:
- 미술관 15곳 (Met, AIC, Louvre, Orsay 등)
- 작가 20명 (Leonardo, Monet, Van Gogh 등)
- 작품 10점 (Met Museum 5점 + Art Institute of Chicago 5점)

### 개별 수집

단계별로 나눠서 실행할 수도 있습니다.

```bash
python3 scripts/ingest_museums.py   # 미술관
python3 scripts/ingest_artists.py   # 작가
python3 scripts/ingest_met_artworks.py   # Met Museum 작품
python3 scripts/ingest_aic_artworks.py   # AIC 작품
```

### 장소(Places) 데이터 upsert

`db data/places.csv` 기반으로 장소 데이터를 DB에 반영합니다.

```bash
python3 scripts/upsert_places.py            # 실제 반영
python3 scripts/upsert_places.py --dry-run  # 미리보기
```

---

## 4. 데이터 추가 방법

### 미술관 추가

`scripts/ingest_museums.py` 의 `MUSEUMS_DATA` 리스트에 항목을 추가합니다.

```python
MUSEUMS_DATA = [
    # 기존 항목들...
    {
        'wikidata_id': 'Q XXXXXXX',          # Wikidata 엔티티 ID
        'name_en': 'Museum Name',
        'name_ko': '미술관 한국어 이름',
        'country_code': 'KR',                # ISO 3166-1 alpha-2
        'city': 'Seoul',
        'latitude': Decimal('37.5665'),
        'longitude': Decimal('126.9780'),
        'website': 'https://example.com',
        'description_en': 'English description',
        'description_ko': '한국어 설명'
    },
]
```

추가 후 실행:

```bash
python3 scripts/ingest_museums.py
```

> Wikidata ID는 https://www.wikidata.org 에서 미술관 이름으로 검색해 확인합니다.

---

### 작가 추가

`scripts/ingest_artists.py` 의 `ARTISTS_DATA` 리스트에 항목을 추가합니다.

```python
ARTISTS_DATA = [
    # 기존 항목들...
    {
        'wikidata_id': 'Q XXXXXXX',          # Wikidata 엔티티 ID
        'name_en': 'Artist Name',
        'name_ko': '작가 한국어 이름',
        'birth_year': 1850,
        'death_year': 1910,                  # 생존 작가는 None
        'nationality': 'French',
        'bio_en': 'English biography',
        'bio_ko': '한국어 작가 소개'
    },
]
```

추가 후 실행:

```bash
python3 scripts/ingest_artists.py
```

---

### 작품 추가

작품은 외부 API(Met Museum / AIC)에서 ID로 가져옵니다.

#### Met Museum 작품 추가

1. https://www.metmuseum.org 에서 작품 페이지 URL의 숫자 ID를 확인합니다.
   - 예시 URL: `https://www.metmuseum.org/art/collection/search/436535` → ID: `436535`

2. `scripts/ingest_met_artworks.py` 의 `sample_object_ids` 리스트에 추가합니다.

```python
sample_object_ids = [
    436535,  # Wheat Field with Cypresses
    # 새 작품 ID 추가
    438722,  # 추가할 작품
]
```

3. 실행:

```bash
python3 scripts/ingest_met_artworks.py
```

> 또는 전체 컬렉션 수집: `python3 scripts/ingest_met_artworks_all.py`

#### Art Institute of Chicago(AIC) 작품 추가

1. https://www.artic.edu 에서 작품 페이지 URL의 숫자 ID를 확인합니다.
   - 예시 URL: `https://www.artic.edu/artworks/27992` → ID: `27992`

2. `scripts/ingest_aic_artworks.py` 의 `aic_artwork_ids` 리스트에 추가합니다.

```python
aic_artwork_ids = [
    27992,   # A Sunday on La Grande Jatte
    # 새 작품 ID 추가
    11434,   # 추가할 작품
]
```

3. 실행:

```bash
python3 scripts/ingest_aic_artworks.py
```

> 또는 전체 컬렉션 수집: `python3 scripts/ingest_aic_artworks_all.py`

---

## 5. DB 관리 명령어

```bash
make docker-up       # PostgreSQL 시작
make docker-down     # PostgreSQL 중지
make docker-restart  # PostgreSQL 재시작
make db-init         # 테이블 생성
make db-reset        # 테이블 전체 초기화 (데이터 삭제)
make logs            # DB 로그 확인
make clean           # 컨테이너 및 볼륨 전체 삭제
```

---

## 프로젝트 구조

```
artmap/
├── docker/
│   └── init-db/01-init.sql      # DB 초기화 SQL
├── docker-compose.yml           # PostgreSQL 컨테이너 설정
├── init_db.py                   # 테이블 생성 스크립트
├── requirements.txt
├── scripts/
│   ├── ingest_all.py            # 전체 수집 마스터 스크립트
│   ├── ingest_museums.py        # 미술관 수집
│   ├── ingest_artists.py        # 작가 수집
│   ├── ingest_met_artworks.py   # Met Museum 작품 수집
│   ├── ingest_met_artworks_all.py
│   ├── ingest_aic_artworks.py   # AIC 작품 수집
│   ├── ingest_aic_artworks_all.py
│   ├── ingest_wikidata_artworks.py
│   ├── geocode_places.py        # 장소 좌표 처리
│   └── upsert_places.py         # 장소 데이터 upsert
├── db data/
│   ├── artworks.csv             # 작품 원본 데이터
│   └── places.csv               # 장소 원본 데이터
└── src/
    ├── reception/               # 데이터 수집/저장 도메인
    └── shared_kernel/           # 공통 인프라 (DB 연결, 로깅)
```
