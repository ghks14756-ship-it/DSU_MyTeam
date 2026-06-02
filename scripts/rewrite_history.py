import os
import sys
import subprocess

if len(sys.argv) > 1 and sys.argv[1] == "editor":
    filepath = sys.argv[2]
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if "git-rebase-todo" in filepath:
        content = content.replace("pick ", "reword ")
    elif "COMMIT_EDITMSG" in filepath:
        translations = {
            "fix: resolve channel override bug, add /상태조회 command, enhance error logging": "fix: 채널 권한 오버라이드 버그 수정, /상태조회 커맨드 추가, 에러 로깅 강화",
            "feat: setup roles, channels, and fix auth": "feat: Discord 서버 역할 및 채널 자동 셋업 구현, 인증 로직 버그 수정",
            "feat: Implement matching engine v2 - priority queue, event-driven, 3-day DM lifecycle": "feat: 매칭 엔진 v2 구현 - 우선순위 큐, 이벤트 기반 처리, 3일 경과 DM 수명주기 적용",
            "Update API URL to cloudflare tunnel": "fix: 프론트엔드 API 호출 주소를 Cloudflare Tunnel 도메인으로 업데이트",
            "Refactor API URLs to use API_BASE_URL constant": "refactor: 하드코딩된 API 주소를 API_BASE_URL 상수를 참조하도록 리팩토링",
            "Fix Vercel build config and update index.html button links": "fix: Vercel 빌드 설정 파일(vercel.json) 수정 및 index.html의 버튼 링크 오류 해결",
            "feat: Add My Profile page and fix UI rendering bugs": "feat: 내 프로필(My Profile) 페이지 UI 추가 및 화면 렌더링 버그 수정"
        }
        for en, ko in translations.items():
            content = content.replace(en, ko)
            
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    sys.exit(0)

def main():
    env = os.environ.copy()
    script_path = os.path.abspath(__file__)
    # Must use double quotes and escape backslashes for Windows env vars if needed,
    # but Python's subprocess handles a list of args better.
    # Actually for git, GIT_EDITOR expects a shell command. 
    # Python executable might have spaces? Let's use sys.executable.
    python_exe = sys.executable.replace('\\', '/')
    script_path_f = script_path.replace('\\', '/')
    
    cmd_str = f'"{python_exe}" "{script_path_f}" editor'
    
    env['GIT_SEQUENCE_EDITOR'] = cmd_str
    env['GIT_EDITOR'] = cmd_str
    
    print("Starting interactive rebase...")
    # Rebase from the very first commit (root)
    subprocess.run(["git", "rebase", "-i", "--root"], env=env)
    print("Rebase completed.")

if __name__ == "__main__":
    main()
