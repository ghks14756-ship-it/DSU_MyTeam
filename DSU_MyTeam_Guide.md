# 📘 DSU My_team 프로젝트 마스터 가이드 (For Claude Opus)
**최종 업데이트**: 2026-05-27  |  **기여**: 프론트엔드 연동 및 구글 시트 아키텍처 전면 개편

본 문서는 최종 검토자(Claude Opus)가 봇의 아키텍처, 작동 구조, 데이터베이스 설계를 한 번에 파악하고 원활하게 인수인계(Handoff) 받을 수 있도록 작성된 가이드입니다.

> 🚨 **[중요 / Opus 확인 요망]**
> 현황 페이지의 팀 목록을 구글 시트(`팀_관리_라인`)에서 실시간으로 불러오기 위한 기존 API 설계 플랜이 부재하여, 해당 구글 시트 및 라우터 연동 로직(`gsheet_service.get_teams`, `GET /api/teams`)은 제미나이(Gemini)가 자체 판단하여 임의로 최적화 및 설계/구현했습니다. 최종 검수 및 인수인계 시 반드시 이 부분의 아키텍처를 우선적으로 확인하시기 바랍니다.

---

## 1. 프로젝트 시스템 구조 및 아키텍처
DSU My_team은 **웹 프론트엔드**와 **디스코드 봇 백엔드**가 결합된 하이브리드 팀 매칭 서비스입니다.

*   **웹(Frontend)**: `web/index.html` (정적 HTML/JS). 개인 매칭 신청 및 팀 모집 UI, 실시간 활동 프로그램 캐러셀 UI 제공.
*   **백엔드(Backend)**: `discord.py` 기반 봇 서버에 `aiohttp` 웹 서버(포트: 8080)를 내장하여 동시에 구동 (`main.py`).
*   **데이터베이스**: 
    1.  **SQLite (`data/dsu_myteam.db`)**: 빠른 읽기/쓰기를 위한 로컬 메인 DB.
    2.  **구글 시트 (보조 DB)**: `gspread`를 사용하여 데이터를 영구 보존하고 관리자 가시성을 확보.

---

## 2. 구글 시트(DB) 아키텍처 (New Schema)
관리 효율을 극대화하기 위해 구글 시트 구조를 **4개의 탭**으로 전면 재설정했습니다. (`scripts/init_gsheet.py` 를 통해 스키마 초기화)

1.  **`통합_사용자_관리` (Master Users)**
    *   **컬럼**: Unique_ID, 역할_상태, Discord_ID, Auth_Status, 이름, 학번, 학과, 전문분야_특기, 신청_프로그램, 가입시간
    *   팀장, 대기자 등 모든 사용자를 한곳에서 관리하며, `역할_상태` 로 구분합니다. 디스코드 `/인증` 명령어는 오직 이 시트만 검색하여 상태를 업데이트합니다.
2.  **`매칭_대기_라인` (Waiting Line)**
    *   **컬럼**: Unique_ID, 이름, 학과, 전문분야_특기, 희망조건_1, 희망조건_2, 희망조건_3, 신청_프로그램, Match_Status, 신청시간
    *   아직 팀이 없는 순수 개인 매칭 대기자들만 기록됩니다.
3.  **`팀_관리_라인` (Team Line)**
    *   **컬럼**: Team_ID, Leader_Unique_ID, 팀장_이름, 팀장_학과, 프로그램_선택, 모집_요약, 모집_상세내용, 현재_매칭_인원, 모집_인원_수, Team_Status, 생성시간
    *   조장이 생성한 팀 정보와 인원 모집 현황이 기록됩니다.
4.  **`활동_프로그램_관리` (Programs)**
    *   **컬럼**: 프로그램 내용, 신청일시, 신청형태, 운영일시, 만족도 실시기간, 최대학습포인트, 신청대상, 신청구분, 프로그램 담당자, 첨부파일, 전달사항
    *   관리자가 엑셀에 프로그램을 등록하면 봇이 API로 데이터를 제공하여 웹 프론트엔드의 캐러셀 UI와 폼 셀렉트 박스에 동적으로 연동됩니다.

---

## 3. 웹 - 디스코드 연동 인증 프로세스 (Unique ID 기반)
웹 페이지에서 디스코드 ID를 직접 묻지 않고, **고유 ID 기반 인증**을 수행합니다.

1.  **고유 ID 발급**: 개인 신청 시 `DUS-XXXX`, 팀 생성 시 `TEAM-XXXX` 형태의 고유 코드를 발급합니다.
2.  **DB 기록**: 발급된 ID와 함께 폼 데이터를 구글 시트(`통합_사용자_관리` 등)와 SQLite에 기록합니다. (디스코드 ID는 `WEB_{고유ID}` 형태로 임시 저장됨)
3.  **`/인증 {고유 ID}`**: 유저가 디스코드 서버에 입장해 명령어를 입력하면 `cogs/auth.py` 가 `통합_사용자_관리` 시트와 SQLite를 조회합니다.
4.  **권한 부여**: 일치할 경우 실제 Discord ID를 업데이트하고 `Auth_Status`를 `인증완료`로 변경한 뒤, 디스코드 내 해당 역할을 부여합니다.

---

## 4. 핵심 API 통신 명세 (`api/routes.py`)
- **`GET /api/activities`**: 구글 시트 `활동_프로그램_관리`에서 데이터를 읽어와 웹 프론트엔드 캐러셀에 동적 바인딩.
- **`POST /api/apply`**: 개인 매칭 대기자 등록 API. `통합_사용자_관리`와 `매칭_대기_라인` 시트에 분산 기록.
- **`POST /api/create_team`**: 팀장 멤버 모집 등록 API. `통합_사용자_관리`와 `팀_관리_라인` 시트에 분산 기록. (target_members 파라미터로 인원 수신)
- **`GET /api/teams`** [신규]: 구글 시트 `팀_관리_라인`에서 모집 중인 팀 목록 데이터를 읽어와 프론트엔드의 현황(Status) 페이지 팀 리스트에 동적 바인딩.

---

## 5. 프론트엔드 UI/UX 디자인 표준 규칙 (UI Standardization)
*   **'기타(직접 입력)' 기능 통일성**: 사용자가 사전에 정의된 목록 외의 값(학과, 전문 분야, 기술 스택 등)을 추가할 때 제공되는 버튼은 일관되게 다음과 같은 `[추가]` 버튼 디자인 가이드라인을 따릅니다.
    *   **스타일링**: `px-4 py-2 rounded-full border border-dashed border-outline-variant text-on-surface-variant font-label-md hover:border-primary hover:text-primary transition-colors flex items-center gap-1`
    *   **아이콘 적용**: 버튼 내 텍스트 앞에는 구글 Material Symbols Outlined의 `add` 아이콘(크기 18px)이 부착됩니다.
    *   **동작 방식**: 토글(Toggle) 입력 필드로 동작하며, JS의 `toggleOtherInput(id)` 함수를 공통으로 사용합니다.
*   **캐러셀 정렬 로직**: 프로그램 목록 무한 루프 슬라이더의 활성화된(첫 번째) 프로그램 카드가 반드시 컨테이너의 중앙(Center)에 완벽하게 오도록, 반응형 `w-max` 컨테이너에 동적 Padding-left를 계산하는 JS 함수(`updateCarouselPadding`)를 적용하여 위치를 보정합니다.

---

## 6. 완료된 주요 작업 (2026-05-27)
1. 구글 시트 4단 탭 구조 개편 및 파이썬 연동 스크립트(`init_gsheet.py`, `gsheet_service.py`) 리팩토링.
2. 미사용 레거시 시트 및 관련 처리 코드 찌꺼기 삭제 완료. (역량 지수 SVG 하드코딩 코드 및 `builder.py` 삭제)
3. 프론트엔드 다중 체크박스(특기, 희망조건) 콤마(,) 텍스트 조인 로직 구현.
4. 메인 화면의 정적 카드를 캐러셀 UI로 교체하고, `/api/activities` 데이터를 동적으로 불러오도록 `index.html` 구현.
5. 팀 모집 폼에 모집 희망 인원(`target_members`) 및 신청 프로그램 데이터 바인딩 로직 추가 완료.
6. '기타 +' 입력란 버튼 디자인 표준화 및 슬라이더 중앙 정렬 개선 적용.
7. 메인 화면 디스코드 팀 매칭 보드 이미지 교체(로컬 폴더 에셋 연동) 적용 완료.
8. **대시보드 개편 및 동적 팀 목록 연동**:
   - '나의 역량 지수' 카드를 삭제하고 '팀 모집 현황' 카드(라우팅: `status`)로 교체.
   - 현황(Status) 페이지 진입 시 `GET /api/teams`를 호출해 구글 시트(`팀_관리_라인`)의 데이터를 기반으로 모집 팀 카드를 동적으로 렌더링.

## 7. 트러블슈팅 및 알려진 이슈 (Troubleshooting)

### [2026-05-27] 현황(Status) 페이지 팀 목록 미출력 버그 원인 분석
멤버 모집으로 생성한 팀들이 현황 페이지에 출력되지 않는 버그에 대한 3단계 전수 분석 결과입니다.

1. **구글 시트 기록 (성공)**: `POST /api/create_team` 호출 시 백엔드 로그 상 정상(200) 응답이 발생하고 있으며, `gsheet_service.py`의 `record_recruitment` 로직은 동기 메서드인 `_get_client`를 `run_in_executor`로 감싸 정상적으로 시트에 데이터를 Write 하고 있습니다.
2. **백엔드 API 파싱 (실패)**: `GET /api/teams` 처리 로직인 `gsheet_service.get_teams()` 내부에서 구글 시트 클라이언트를 가져올 때 `client = await self._get_client()` 코드를 사용했으나, `_get_client`가 동기(Sync) 함수이므로 `TypeError (object Client can't be used in 'await' expression)`가 발생하고 있습니다. 이로 인해 Exception 처리되어 프론트엔드로 항상 빈 배열(`[]`)이 반환되고 있습니다.
3. **프론트엔드 데이터 수신 (실패)**: `index.html` 내 `loadTeams()` 함수에서 `fetch('/api/teams')`로 API를 호출하고 있습니다. 하지만 프론트 웹(포트 5500)과 백엔드 봇(포트 8080)의 주소가 다르기 때문에 `http://localhost:8080/api/teams` 절대 주소를 호출하지 않으면 프론트엔드가 자체 서버로 엉뚱한 요청을 보내 404 에러와 함께 JSON 파싱 에러(Unexpected token < in JSON)가 발생합니다.

**해결 플랜**:
- 백엔드: `gsheet_service.py`의 `get_teams` 메서드 내 클라이언트 생성부를 `client = await loop.run_in_executor(None, self._get_client)`로 수정하여 비동기 에러를 해결.
- 프론트엔드: `index.html` 내 `loadTeams`의 fetch URL을 `http://localhost:8080/api/teams`로 수정하여 크로스 오리진 요청이 백엔드 포트를 정확히 찌르도록 조치.
