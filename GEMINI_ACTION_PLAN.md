# 📋 DSU MyTeam — 제미나이(Gemini) 전달용 코딩 계획서 (Action Plan)

> **작성자**: Claude Sonnet (Thinking)  
> **작성일**: 2026-06-02  
> **대상**: 제미나이(Gemini Pro / Flash) — 다음 교대 AI 코딩 어시스턴트  
> **목적**: 현재 프로젝트 상태를 100% 파악하고, 다음 작업 단계를 교차 검증하기 위한 설계서

---

## 🗺️ 1. 프로젝트 전체 아키텍처 요약

### 시스템 구성도

```
[사용자 브라우저]
    └── web/index.html  (정적 SPA, TailwindCSS + Vanilla JS)
          │
          │  fetch() — HTTP 요청 (포트: 8080)
          ▼
[Python 백엔드: main.py]
    ├── discord.py 봇 서버 (Discord API)
    └── aiohttp 내장 웹서버 (Port: 8080)
          │
          ├── api/routes.py  (라우터: GET/POST 핸들러)
          │
          └── services/gsheet_service.py  (구글 시트 DB 연동)
                │
                └── [구글 시트 (보조 DB)]
                      ├── 통합_사용자_관리 (인증/사용자 원장)
                      ├── 매칭_대기_라인 (개인 매칭 대기자)
                      ├── 팀_관리_라인 (팀장 모집 정보)
                      ├── 활동_프로그램_관리 (프로그램 카탈로그)
                      └── 회원_정보 (웹 회원가입 정보)
```

### 핵심 설계 원칙
- **SPA 방식**: 단일 `web/index.html` 파일 내에서 `navigate(pageId)` 함수로 `div.page` 섹션들을 show/hide
- **비동기 DB 패턴**: `gsheet_service.py`의 모든 함수는 `loop.run_in_executor(None, _sync_func)` 패턴으로 동기 gspread를 비동기 aiohttp에서 안전하게 호출
- **CORS 완전 허용**: `Access-Control-Allow-Origin: *`로 개발 환경 허용
- **API_BASE_URL**: 프론트엔드 JS 전역 변수 `const API_BASE_URL = 'http://localhost:8080'` (배포 시 수동 변경 필요)

---

## 📊 2. 현재 작업 완료 현황

| 화면/기능 | 상태 | 비고 |
|---|---|---|
| 대시보드 (page-dashboard) | ✅ 완료 | Figma 시안 기반 12카드 레이아웃, `loadDashboardPrograms()` 동적 렌더링 |
| 현황 페이지 (page-status) | ✅ 완료 | 3단 레이아웃(좌필터/중리스트/우버튼), `loadTeams()` 동적 바인딩 |
| 매칭 신청 1단계 (page-apply-step1) | ✅ 완료 | 대분류 카테고리 → 소분류 캐러셀 2단계 선택 UI |
| 매칭 신청 2단계 (page-apply-step2) | ✅ 완료 | 주간 시간표 그리드 + 연락수단 + 희망조건 |
| 멤버 모집 1단계 (page-recruit-step1) | ✅ 완료 | 팀장 정보 입력 폼 |
| 멤버 모집 2단계 (page-recruit-step2) | ✅ 완료 | 기술스택 태그 + 모집 인원 수 카운터 + 요약 |
| 키카드 발급 결과 (page-keycard) | ✅ 완료 | 신청 완료 후 Unique ID 표출 화면 |
| 내정보 페이지 (page-profile) | ✅ 완료 | 프로필 조회/수정, 주간 시간표 |
| 로그인/회원가입 모달 (auth-modal) | ✅ 완료 | 아이디 로그인 / 인증키 로그인 / 회원가입 탭 분리 |
| `loadDashboardPrograms()` | ✅ **버그 수정 완료** | 전역 스코프 이동, `DOMContentLoaded`에서 호출, `insertAdjacentHTML` 방식으로 렌더링 |
| `navigate()` 함수 | ✅ 완료 | 로그인 검증 로직 주석 처리(개발 모드), 페이지 전환 + 네비바 활성화 처리 |
| `GET /api/activities` | ✅ 완료 | gsheet → 프로그램 목록 반환 |
| `GET /api/teams` | ✅ 완료 | gsheet 팀_관리_라인 데이터 반환 |
| `POST /api/apply` | ✅ 완료 | 개인 매칭 신청 → SQLite + gsheet 기록 |
| `POST /api/create_team` | ✅ 완료 | 팀 모집 등록 → SQLite + gsheet 기록 |
| `POST /api/signup`, `/api/login` | ✅ 완료 | 웹 회원가입/로그인 시스템 |
| `GET /api/my-status`, `/api/my-profile` | ✅ 완료 | 내 매칭 현황 + 내정보 조회/수정 |

---

## 🚨 3. 현재 남아있는 버그 및 미완성 기능 목록

### [BUG-01] ✅ (해결) 대시보드 `loadDashboardPrograms` — fetch URL 불일치
- **위치**: `web/index.html`, 약 line 1161
- **코드**: `const res = await fetch('/api/activities');`
- **문제**: 로컬 개발 환경에서 `web/index.html`은 VSCode Live Server(포트 5500 등)로 서빙됨.  
  이 경우 `/api/activities` 는 `http://localhost:5500/api/activities`로 요청되어 **404** 발생.
- **올바른 코드**: `const res = await fetch(API_BASE_URL + '/api/activities');`  
  (다른 모든 fetch 호출은 이미 `API_BASE_URL`을 사용하는데, 이 함수만 누락됨)
- **우선순위**: 🔴 **최우선 수정 필요** — 대시보드 카드가 아예 안 뜨는 현상의 원인

### [BUG-02] ✅ (해결) 현황 페이지 — `team-list-container` ID 불일치
- **위치**: `web/index.html`
  - `loadTeams()` 함수 (약 line 1268): `getElementById('team-list-container')`를 탐색
  - Status 페이지 HTML (약 line 947): 컨테이너 ID가 `team-list-container-static`으로 선언됨
- **문제**: ID 불일치로 인해 `loadTeams()`가 항상 `null`을 반환하고 팀 목록이 렌더링되지 않음
- **수정**: HTML의 `id="team-list-container-static"`을 `id="team-list-container"`로 변경 또는 JS의 `getElementById` 대상을 일치시킴
- **우선순위**: 🟡 중요

### [BUG-03] ✅ (해결) `navigate('status')` 호출 시 `loadTeams()` 미호출
- **위치**: `web/index.html`, `navigate()` 함수 내부 (약 line 964-1050)
- **문제**: `navigate('profile')` 호출 시에는 `loadProfile()`을 호출하는 로직이 있음.  
  그러나 `navigate('status')` 호출 시 `loadTeams()`를 트리거하는 코드가 없음.
- **수정**: `navigate()` 함수 내에 아래 블록 추가:
  ```javascript
  if (pageId === 'status') {
      loadTeams();
  }
  ```
- **우선순위**: 🟡 중요

### [BUG-04] ✅ (해결) `loadDashboardPrograms`의 데이터 파싱 — 구글 시트 원시 컬럼명 불일치
- **위치**: `web/index.html`, `loadDashboardPrograms()` 함수 (약 line 1144)
- **문제**: 이 함수는 `data[].name`, `data[].description`, `data[].max_members`를 참조함.  
  그런데 `GET /api/activities`는 gsheet의 **원시 컬럼명** (예: `프로그램 내용`, `전달사항`, `최대학습포인트`)을 그대로 반환함.  
  `gsheet_service.get_programs()`는 `sheet.get_all_records()`를 그대로 반환하여 변환이 없음.
- **해결 방안 (2가지 중 선택)**:  
  - **Option A (권장)**: `api/routes.py`의 `api_activities` 핸들러에서 컬럼명을 camelCase로 변환 후 반환.  
  - **Option B**: `loadDashboardPrograms()`의 `makeCard` 함수에서 `item['프로그램 내용']` 등 한글 컬럼명으로 직접 접근 (이미 카드 HTML에서 `item.name || '제목 없음'`과 `item['전달사항']`을 둘 다 fallback으로 사용 중 → 부분 동작 가능).
- **우선순위**: 🟡 중요 (데이터 표출 완성도에 영향)

### [BUG-05] 🟢 `loadDashboardPrograms`의 카테고리 분류 기준 — 시트 컬럼 존재 여부 미확인
- **위치**: `web/index.html`, 약 line 1220
- **코드**: `const cat = (item['카테고리별 분류'] || '').trim();`
- **문제**: `활동_프로그램_관리` 시트에 `카테고리별 분류` 컬럼이 실제로 존재하는지 확인 필요.  
  `add_gsheet_category.py` 스크립트가 이 컬럼을 추가하는 용도로 보이나 적용 여부 불명확.
- **우선순위**: 🟢 낮음 (기능 자체는 동작, 다만 카테고리 분류가 안될 수 있음)

---

## 🛠️ 4. 다음 작업 단계 — 제미나이에게 요청하는 구체적 코딩 작업

> 아래 작업들은 **우선순위 순**으로 정렬되어 있으며, 각 작업은 독립적으로 수행 가능합니다.

---

### ✅ [TASK-01] (완료) BUG-01 수정 — `loadDashboardPrograms` fetch URL 교정

**파일**: `web/index.html`

**변경 내용**:
```javascript
// 현재 (잘못된 코드) — 약 line 1161
const res = await fetch('/api/activities');

// 수정 후 (올바른 코드)
const res = await fetch(API_BASE_URL + '/api/activities');
```

**작업 난이도**: ⭐ (매우 쉬움 — 1줄 수정)

---

### ✅ [TASK-02] (완료) BUG-02 + BUG-03 수정 — 현황 페이지 팀 목록 완전 연동

**파일**: `web/index.html`

**변경 내용 1**: HTML ID 수정 (약 line 947)
```html
<!-- 현재 -->
<div class="grid grid-cols-1 gap-4" id="team-list-container-static">

<!-- 수정 후 -->
<div class="grid grid-cols-1 gap-4" id="team-list-container">
```

**변경 내용 2**: `navigate()` 함수 내 status 진입 시 `loadTeams()` 호출 추가 (약 line 998-1001 블록 근처)
```javascript
// 프로필 페이지 로드 (기존 코드)
if (pageId === 'profile') {
    loadProfile();
}

// 아래 블록 추가
if (pageId === 'status') {
    loadTeams();
}
```

**작업 난이도**: ⭐⭐ (쉬움 — 2곳 수정)

---

### ✅ [TASK-03] (완료) BUG-04 수정 — API 응답 데이터 정규화 (컬럼명 통일)

**파일**: `api/routes.py`

**변경 내용**: `api_activities` 핸들러에서 gsheet 원시 컬럼명을 프론트엔드 JS가 기대하는 camelCase 키로 변환

```python
@routes.get('/api/activities')
async def api_activities(request: web.Request):
    bot = request.app['bot']
    try:
        raw = await bot.gsheet.get_programs()
        # 컬럼명 정규화 (프론트엔드 JS 기대값에 맞춤)
        programs = []
        for p in raw:
            programs.append({
                "name": p.get("프로그램 내용", ""),
                "description": p.get("전달사항", ""),
                "deadline": p.get("신청일시", ""),
                "max_members": int(p.get("최대학습포인트", 0) or 0),
                "category": p.get("카테고리별 분류", ""),
                "target": p.get("신청대상", ""),
                "type": p.get("신청형태", ""),
                "manager": p.get("프로그램 담당자", ""),
                "image": p.get("첨부파일", ""),
                # 원본 데이터도 유지 (다른 곳에서 활용 가능)
                "프로그램 내용": p.get("프로그램 내용", ""),
                "전달사항": p.get("전달사항", ""),
                "신청일시": p.get("신청일시", ""),
                "카테고리별 분류": p.get("카테고리별 분류", ""),
            })
        return add_cors_headers(web.json_response({"success": True, "data": programs}))
    except Exception as e:
        log.error(f"프로그램 목록 로드 실패: {e}")
        return add_cors_headers(web.json_response({"success": False, "error": str(e)}, status=500))
```

**주의사항**:
- 원본 한글 키도 함께 포함시켜 `renderCarousel()` 같은 기존 함수들이 `prog['프로그램 내용']`으로 접근하는 코드가 깨지지 않도록 처리.
- `loadDashboardPrograms()`의 카테고리 필터는 `item['카테고리별 분류']` 사용 중 → `카테고리별 분류` 키 유지 필수.

**작업 난이도**: ⭐⭐⭐ (중간 — 라우터 로직 변경, 하위 호환성 고려 필요)

---

### ✅ [TASK-04] (완료) UX 개선 — 대시보드 우측 사이드바 로그인 상태 연동

**파일**: `web/index.html`

**현재 상태**: 대시보드 우측 사이드바의 프로필 카드가 하드코딩된 "김ㅁㅁ씨 환영합니다" 텍스트를 표출 중.

**구현 목표**: 
- 비로그인 상태: 로그인 버튼 카드 표출
- 로그인 상태: `localStorage`의 `nickname`을 읽어 `[닉네임]씨 환영합니다` 동적 표출

**구현 방법**:
1. `checkLoginState()` 함수 내에 사이드바 닉네임 업데이트 로직 추가
2. `navigate('dashboard')` 호출 시 `checkLoginState()` 실행 보장

**작업 난이도**: ⭐⭐ (쉬움)

---

### 🟢 [TASK-05] 로그인 검증 로직 재활성화 (선택적, 개발 완료 후 적용)

**파일**: `web/index.html`, `navigate()` 함수 약 line 965-971

**현재 상태**: 아래 코드가 주석 처리된 상태
```javascript
// const requireLoginPages = ['apply-step1', 'apply-step2', 'recruit-step1', 'recruit-step2', 'profile'];
// if (requireLoginPages.includes(pageId) && !localStorage.getItem('unique_id')) {
//     alert('로그인이 필요한 서비스입니다.');
//     if (typeof openAuthModal === 'function') openAuthModal();
//     return;
// }
```

**조건**: TASK-01~03 완료 및 서버 실제 가동 확인 후 주석 해제 적용.

---

## 📌 5. 코딩 작업 시 반드시 준수할 규칙 (전 AI 공통 수칙)

1. **코드 선행 확인 필수**: 어떤 수정이든 반드시 해당 파일의 실제 코드를 먼저 읽고 현재 상태를 확인한 뒤 작업할 것. 기억에 의존하지 말 것.
2. **제안서 작성 및 피드백 수렴**: 대규모 변경은 반드시 계획서를 먼저 작성하고 사용자 승인을 받을 것. 단, 사용자가 "바로 해라"고 허가하면 즉시 실행.
3. **지시한 것만**: 오버엔지니어링 금지. 지시하지 않은 UI 개편, 불필요한 파일 생성, 없어도 되는 리팩토링 절대 금지.
4. **인수인계 철저**: 작업 완료 후 반드시 `DSU_MyTeam_Progress.md`의 Change Log에 날짜, 작업 내용, 수정 파일을 기록할 것.

---

## 🔍 6. 파일 구조 참조 (빠른 탐색용)

```
DSU_MyTeam/
├── web/
│   └── index.html          ← 메인 SPA 파일 (2112줄, 모든 화면 + JS 포함)
├── api/
│   └── routes.py           ← aiohttp 라우터 (GET/POST API 핸들러)
├── services/
│   └── gsheet_service.py   ← 구글 시트 연동 서비스 (901줄)
├── cogs/
│   └── (discord.py cogs)
├── database/               ← SQLite DB 관련
├── main.py                 ← 봇 + 웹서버 동시 실행 진입점
├── config.py               ← 환경변수 설정 (.env 파일 연동)
├── .env                    ← DISCORD_TOKEN, GSHEET_SPREADSHEET_ID 등
├── credentials.json        ← 구글 서비스 계정 키
├── DSU_MyTeam_Progress.md  ← 📖 통합 진행 상황 (반드시 읽을 것)
├── DSU_MyTeam_Guide.md     ← 📖 마스터 가이드 (아키텍처 상세)
└── GEMINI_ACTION_PLAN.md   ← 📋 본 문서
```

---

## ✅ 7. 작업 우선순위 요약

| 순위 | Task | 파일 | 난이도 | 예상 효과 |
|:---:|---|---|:---:|---|
| 1 | TASK-01: fetch URL 수정 | index.html | ⭐ | 대시보드 카드 즉시 복구 |
| 2 | TASK-02: 팀 목록 ID 수정 + navigate 연동 | index.html | ⭐⭐ | 현황 페이지 팀 목록 즉시 복구 |
| 3 | TASK-03: API 응답 정규화 | routes.py | ⭐⭐⭐ | 데이터 표출 완성도 향상 |
| 4 | TASK-04: 사이드바 로그인 상태 연동 | index.html | ⭐⭐ | UX 품질 향상 |
| 5 | TASK-05: 로그인 가드 재활성화 | index.html | ⭐ | 최종 배포 준비 |
