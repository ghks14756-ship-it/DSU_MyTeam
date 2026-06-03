# DSU MyTeam — 개발 가이드 & 인수인계 문서

> 최종 업데이트: 2026-06-03  
> 작성자: Antigravity (AI 코딩 어시스턴트)

---

## ⚠️ AI/다른 개발자가 절대 건드리면 안 되는 영역

### 🚫 CRITICAL — 손대지 말 것

| 파일/영역 | 이유 |
|---|---|
| `database/db_manager.py` > `_create_tables()` | 스키마 변경 시 기존 DB 전체 파괴. **ALTER TABLE만 사용** |
| `cogs/random_match.py` > `build_teams()` | 명세서 규칙 1·2·3 정밀 구현. 로직 변경 시 매칭 순서 파괴 |
| `api/routes.py` > CORS 헤더 (`add_cors_headers`) | 웹 ↔ 봇 통신 차단됨 |
| `.env` (로컬) | 봇 토큰, OAuth2 크레덴셜 포함. **절대 커밋 금지** |
| `credentials.json` | Google OAuth2 서비스 계정 키. **절대 커밋 금지** |
| `config.py` > `DEFAULT_TEAM_SIZE = 4` | 팀 기본 정원. 변경 시 매칭 로직 전체 오작동 |

---

## 🏗️ 시스템 아키텍처

```
[웹 브라우저: localhost:3000]
        ↕ HTTP (정적 파일: web/index.html)
[python -m http.server 3000]

[웹 브라우저] ──── API 요청 ────▶ [aiohttp API 서버: :8080]
                                         ↕
                               [Discord Bot (discord.py)]
                                    ↕         ↕
                           [SQLite DB]   [Google Sheets]
                         data/dsu_myteam.db
```

### 핵심 파일 역할표

| 파일 | 역할 |
|---|---|
| `main.py` | 봇 진입점. Cog 로드, aiohttp 서버 시작 |
| `config.py` | 전역 상수 (팀 크기, 채널명, 인터벌 등) |
| `database/db_manager.py` | SQLite 비동기 ORM. 모든 DB 연산의 단일 진입점 |
| `api/routes.py` | aiohttp 라우터. 웹 ↔ 봇 통신 인터페이스 |
| `cogs/random_match.py` | **핵심 매칭 엔진**. 자동 매칭, DM 발송, 만료 처리 |
| `cogs/admin.py` | 관리자 슬래시 커맨드 |
| `cogs/auth.py` | Discord 인증 연동 |
| `services/gsheet_service.py` | 구글 시트 CRUD (캐싱 포함) |
| `web/index.html` | 전체 웹 프론트엔드 (SPA) |

---

## 📐 매칭 시스템 명세 (절대 준수 사항)

### 기본 원칙
- **팀 정원: 4명** (팀장 포함)
- **처리 우선순위**: 자동 랜덤/조건 매칭 > 팀장 수동 모집
- **선착순 기준**: `applied_at` 타임스탬프 ASC (DB 쿼리 레벨에서 보장)
- **프로그램 독립 매칭**: 같은 `program` 값끼리만 매칭 (다른 프로그램 혼합 금지)

### 유저 타입별 처리

| 타입 | `is_leader` | `has_conditions` | 처리 방식 |
|---|---|---|---|
| 일반 랜덤 대기자 | 0 | 0 | FIFO 4명 묶음 |
| 조건 대기자 | 0 | 1 | 동일 조건 큐 (7일 미매칭 시 실패 처리) |
| 팀장 (조건 없음) | 1 | 0 | 대기자 중 자동 배정 |
| 팀장 (조건 있음) | 1 | 1 | 조건 부합 대기자만 배정 |

### Discord ID 체계
- **웹 신청자**: `WEB_{unique_id}_{timestamp}` 형식 (디스코드 미연동)
- **디스코드 연동 완료**: 실제 Discord User ID (숫자)
- **매칭 엔진은 `WEB_`로 시작하는 ID를 자동 제외** (미인증 사용자)

---

## 🔄 주요 플로우

### 매칭 신청 플로우
```
웹 신청 → POST /api/apply → DB applications 저장 (program 포함)
   ↓ (1분 주기 자동 실행)
MatchEngineCog._run_match_cycle()
   ↓
프로그램별 그룹핑 → build_teams() → execute_match_for_teams()
   ↓
팀 채널 생성 → DB 업데이트 → 교차 DM 발송
```

### 팀장 수동 모집 플로우
```
웹 팀등록 → POST /api/create_team → DB applications (is_leader=1) 저장
   ↓
"신청자 목록 확인" 클릭 → GET /api/team-applicants
   ↓
"가입 승인" 클릭 → POST /api/approve-member
   ↓ (pending_approval = 1 설정)
Discord DM 발송 (신청자에게 ✅/❌ 버튼)
   ↓
수락 → PendingApprovalView.accept() → 매칭 완료
거부 or 24h 만료 → clear_pending_approval() → 대기열 복귀
```

### DM 발송 체계
- **매칭 완료 DM**: `_send_cross_dms()` — 팀원 간 교차 정보 공유
- **3일 경과 DM**: `_send_day3_dm()` — 계속진행/조건포기/취소 버튼
- **7일 만료 DM**: `_send_expiry_dm()` — 매칭 실패 알림 + 대기열 삭제
- **팀 가입 초대 DM**: `PendingApprovalView` — 팀장 수동 승인용
- **24h pending 만료**: `_run_pending_expiry_check()` — 대기열 자동 복귀

---

## 🗄️ DB 스키마 요약 (applications 테이블)

```sql
CREATE TABLE applications (
    id INTEGER PRIMARY KEY,
    discord_id TEXT NOT NULL,       -- WEB_{uid} or Discord_ID
    username TEXT NOT NULL,
    student_id TEXT,
    department TEXT,
    skill TEXT,
    activity_id INTEGER,
    program TEXT DEFAULT '',        -- ★ 프로그램별 독립 매칭 핵심
    group_code TEXT,
    applied_at TEXT,                -- ★ FIFO 선착순 기준 (ISO8601)
    expires_at TEXT,                -- 7일 후 만료
    contact TEXT,
    weekly_schedule TEXT,
    has_conditions INTEGER DEFAULT 0,
    conditions TEXT DEFAULT '[]',
    is_matched INTEGER DEFAULT 0,
    is_leader INTEGER DEFAULT 0,    -- ★ 팀장 여부
    day3_dm_sent INTEGER DEFAULT 0,
    expiry_dm_sent INTEGER DEFAULT 0,
    pending_approval INTEGER DEFAULT 0,      -- ★ 팀장 수동 초대 대기
    pending_team_leader_id TEXT DEFAULT NULL,
    pending_since TEXT DEFAULT NULL          -- 24h 만료 기준
);
```

---

## 🌐 Vercel 배포 제한사항 및 주의점

### ✅ 가능한 것
- `web/index.html` 정적 파일 배포 (Vercel Static)
- 이미 `vercel.json`에 라우팅 설정 완료

### ⚠️ 불가능한 것 (Vercel에서 실행 안 됨)
| 기능 | 이유 |
|---|---|
| 봇 서버 (`main.py`) | Vercel은 Python 장기 실행 불가. 별도 서버 필요 |
| API 서버 (`:8080`) | aiohttp 서버는 Vercel Serverless 함수로 변환 필요 |
| Discord Bot | 24/7 실행 필요 → VPS/Render/Railway 사용 |
| Google Sheets 연동 | 서버 측 코드. 웹에서 직접 호출 불가 |

### 🔧 권장 배포 구성
```
[Vercel]  ← web/index.html (정적 프론트엔드)
    ↓ API 요청 (CORS 필요)
[Render / Railway / VPS]  ← main.py (봇 + API 서버)
```

> **중요**: `web/index.html` 내의 `API_BASE_URL`을 배포 서버 주소로 변경해야 함
> 현재: `const API_BASE_URL = 'http://localhost:8080';` (로컬 개발용)

---

## 🔑 환경변수 목록 (`.env.example` 참조)

```env
DISCORD_BOT_TOKEN=          # 봇 토큰 (절대 공개 금지)
GSHEET_SPREADSHEET_ID=      # 구글 시트 ID
GOOGLE_CREDENTIALS_JSON=    # credentials.json 내용 (배포 환경용)
```

---

## 📁 .gitignore 확인 (커밋 금지 파일)

```
.env                 ← 봇 토큰 포함
credentials.json     ← Google OAuth2 키
*.db                 ← SQLite DB (로컬 전용)
bot.log              ← 로그 파일
__pycache__/
data/                ← 로컬 DB 저장 폴더
.vercel              ← Vercel 빌드 캐시
```

---

## 🛠️ 로컬 개발 실행 방법

```bash
# 1. 봇 + API 서버 시작
python main.py

# 2. 웹 프론트엔드 서버 시작 (별도 터미널)
cd web && python -m http.server 3000

# 3. 브라우저에서 접속
# http://localhost:3000
```

---

## 📋 현재까지 구현된 기능 목록

| 기능 | 상태 |
|---|---|
| 웹 로그인 (ID 기반) | ✅ |
| 매칭 신청 (1~3단계) | ✅ |
| 팀 등록 (팀장 모집) | ✅ |
| Discord 인증 연동 | ✅ |
| 자동 매칭 (FIFO, 프로그램별) | ✅ |
| 매칭 완료 DM 교차 발송 | ✅ |
| 3일 경과 알림 DM | ✅ |
| 7일 만료 처리 + 알림 | ✅ |
| 팀장 수동 모집 대시보드 | ✅ |
| 가입 승인 DM (24h 만료) | ✅ |
| 팀 비공개 채널 자동 생성 | ✅ |
| 구글 시트 동기화 | ✅ |
| Discord 서버 입장 가이드 | ✅ |
| 관리자 슬래시 커맨드 | ✅ |

---

## ⏳ 미구현 (Phase 2 예정)

- 팀장 대시보드 조건 매칭 자동 배부 (규칙 2-1)
- Top10 슬라이딩 노출 (규칙 3-2)
- 프로덕션 배포 환경 `API_BASE_URL` 자동 전환
