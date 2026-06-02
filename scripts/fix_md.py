import re

with open('DSU_MyTeam_Progress.md', 'r', encoding='utf-8') as f:
    c = f.read()

# The string to remove
bad_string = '''
### 📅 2026-06-02 (Antigravity - UI/UX 개선 및 버그 수정 세션)
*   **[메인 홈페이지 슬라이드 & 카드 디자인 개선]**
    *   **슬라이드 무한 루프 복구**: 브라우저 기본 스크롤 방식에서 기존의 자바스크립트 DOM 이동(무한 루프) 방식으로 복원. 카드가 끝에 도달하면 부드럽게 첫 번째 카드로 순환 연결됨.
    *   **카드 중앙 정렬 및 여백 계산**: 화살표 클릭 시 뷰포트 중앙에 타겟 카드가 완벽히 정렬되도록 컨테이너 및 아이템의 동적 스크롤 위치 계산 로직 적용.
    *   **카드 텍스트 최적화**: 텍스트 말줄임표(line-clamp)를 제거하고 `break-keep`을 적용하여 자연스러운 줄바꿈 유도. 카드 내부 패딩과 폰트 크기를 컴팩트하게 조절하고, 불필요한 사업단 연락처 정보 삭제 완료.
*   **[가입 신청(Apply) & 멤버 모집(Recruit) 입력 폼 고도화]**
    *   **직접 입력 폼 UI 복구**: Recruit 탭 내 '학부 및 학과' 입력 시 HTML wrapper 태그 누락으로 인한 스크립트 오작동 버그 수정 및 UI 정상화.
    *   **'입력 완료' 버튼 명시**: 각 폼의 커스텀 입력칸(전문 분야, 학과 등) 옆에 직관적인 [입력 완료]/[확인] 버튼 일괄 추가 완료.
*   **[동적 태그(뱃지) 시스템 전면 개편]**
    *   **새로운 추가 로직**: 사용자가 직접 스킬을 입력하고 추가 시(`addCustomSkill`, `addTechTag`), 텍스트 입력창이 숨겨지며 자동으로 새 보라색 태그가 생성되도록 자바스크립트 기능 완성.
    *   **토글(Toggle) 로직 제거 및 삭제 전용 UX**: 체크박스 클릭 시 색깔이 변하는 혼동 유발 로직 완전 제거. 모든 태그는 '활성화' 상태로 고정되며, 호버(Hover) 시 나타나는 **[X] 닫기 아이콘**을 통해서만 태그가 삭제되도록 일관된 모던 UI 적용 완료.

'''

# Remove all insertions
c = c.replace(bad_string, '')

# Now insert it exactly once before "## 📝 4"
target = '## 📝 4. 다음 작업 모델을 위한 연동 및 코딩 보고사항 (Next Actions)'
c = c.replace(target, bad_string + '\n---\n\n' + target)

with open('DSU_MyTeam_Progress.md', 'w', encoding='utf-8') as f:
    f.write(c)
