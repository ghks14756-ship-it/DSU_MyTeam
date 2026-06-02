import re

file_path = r'c:\Users\user\.gemini\antigravity-ide\scratch\DSU_MyTeam\web\index.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace Dashboard
dashboard_pattern = re.compile(r'(<div id="page-dashboard" class="page">).*?(<!-- ============================== -->\s*<!-- 화면명: 매칭 신청 1단계)', re.DOTALL)
dashboard_replacement = r'''\1
        <section class="w-full mb-gutter relative">
            <div class="flex items-center justify-between mb-4 px-2">
                <h2 class="font-headline-lg text-headline-lg text-primary">진행 중인 팀 현황</h2>
            </div>
            <div class="relative w-full overflow-hidden rounded-xl border border-outline-variant/30 card-shadow min-h-[300px] bg-white">
                <div id="dashboard-active-teams-container" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-6">
                    <div class="w-full flex items-center justify-center col-span-full h-48 text-on-surface-variant">진행 중인 팀 데이터를 불러오는 중입니다...</div>
                </div>
            </div>
        </section>

        <!-- Fork Dashboard Section -->
        <section class="w-full mb-8">
            <div class="flex items-center justify-between mb-4 px-2">
                <h2 class="font-headline-lg text-headline-lg text-primary">팀 매칭 시작하기</h2>
                <p class="font-body-md text-on-surface-variant">원하시는 활동 방향을 선택해주세요.</p>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-gutter">
                <div class="bg-white rounded-xl p-8 card-shadow border border-surface-container flex flex-col justify-between hover:-translate-y-1 transition-transform duration-300 bg-gradient-to-br from-white to-primary-container/20 cursor-pointer" onclick="navigate('apply-step1')">
                    <div class="w-16 h-16 rounded-full bg-primary-container text-primary flex items-center justify-center mb-6 shadow-sm">
                        <span class="material-symbols-outlined text-3xl" style="font-variation-settings: 'FILL' 1;">person_add</span>
                    </div>
                    <div>
                        <h3 class="font-headline-md text-headline-md text-on-surface mb-3">개인 매칭 신청</h3>
                        <p class="font-body-md text-on-surface-variant mb-6">본인의 역량과 강점을 등록하고, 최적의 팀원을 찾거나 진행 중인 팀에 지원하세요.</p>
                    </div>
                    <button class="w-full py-4 rounded-xl bg-primary text-on-primary font-headline-sm shadow-md hover:bg-primary/90 transition-colors flex items-center justify-center gap-2">
                        매칭 신청하러 가기
                        <span class="material-symbols-outlined">arrow_forward</span>
                    </button>
                </div>
                
                <div class="bg-white rounded-xl p-8 card-shadow border border-surface-container flex flex-col justify-between hover:-translate-y-1 transition-transform duration-300 bg-gradient-to-br from-white to-secondary-container/20 cursor-pointer" onclick="navigate('recruit-step1')">
                    <div class="w-16 h-16 rounded-full bg-secondary-container text-secondary flex items-center justify-center mb-6 shadow-sm">
                        <span class="material-symbols-outlined text-3xl" style="font-variation-settings: 'FILL' 1;">group_add</span>
                    </div>
                    <div>
                        <h3 class="font-headline-md text-headline-md text-on-surface mb-3">팀원 모집 시작</h3>
                        <p class="font-body-md text-on-surface-variant mb-6">프로젝트 아이디어가 있으신가요? 직접 팀장이 되어 새로운 팀원을 모집해 보세요.</p>
                    </div>
                    <button class="w-full py-4 rounded-xl bg-secondary text-on-secondary font-headline-sm shadow-md hover:bg-secondary/90 transition-colors flex items-center justify-center gap-2">
                        팀장으로 시작하기
                        <span class="material-symbols-outlined">arrow_forward</span>
                    </button>
                </div>
            </div>
        </section>
    </div>

    \2'''
content = dashboard_pattern.sub(dashboard_replacement, content)

# 2. Replace Apply Step 1 Program Selection
apply_prog_pattern = re.compile(r'(<!-- Program Selection Card -->\s*<div class="[^"]*rounded-xl p-6[^"]*">).*?(<!-- Specialty/Major Selection Card -->)', re.DOTALL)
apply_prog_replacement = r'''\1
                    <h2 class="font-headline-sm text-headline-sm text-on-surface mb-stack-md flex items-center gap-2">
                        <span class="material-symbols-outlined text-primary" style="font-variation-settings: 'FILL' 1;">grid_view</span>
                        프로그램 선택
                    </h2>
                    
                    <div class="mb-6">
                        <label class="block font-label-md text-label-md text-on-surface-variant mb-2">1단계: 대분류 카테고리 선택</label>
                        <select id="apply-category-select" class="w-full bg-surface-container-low border border-outline-variant/50 rounded-lg px-4 py-3 font-body-md text-body-md focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all appearance-none cursor-pointer" onchange="filterPrograms('apply')">
                            <option value="">카테고리를 선택하세요</option>
                        </select>
                    </div>

                    <div class="relative group px-12" id="apply-program-container" style="display: none;">
                        <label class="block font-label-md text-label-md text-on-surface-variant mb-2 -ml-12">2단계: 상세 프로그램 선택</label>
                        <button class="absolute left-0 top-1/2 -translate-y-1/2 z-10 w-10 h-10 rounded-full bg-white shadow-lg border border-outline-variant/30 flex items-center justify-center text-primary hover:bg-surface-container transition-all md:opacity-0 md:group-hover:opacity-100 hidden md:flex" onclick="scrollFormCarousel(this, 'prev')" type="button">
                            <span class="material-symbols-outlined">chevron_left</span>
                        </button>
                        <div class="w-full overflow-hidden" id="apply-carousel-wrapper">
                            <div class="carousel-container flex gap-4 pb-2 transition-transform duration-300 w-max" id="apply-program-carousel-track">
                            </div>
                        </div>
                        <button class="absolute right-0 top-1/2 -translate-y-1/2 z-10 w-10 h-10 rounded-full bg-white shadow-lg border border-outline-variant/30 flex items-center justify-center text-primary hover:bg-surface-container transition-all md:opacity-0 md:group-hover:opacity-100 hidden md:flex" onclick="scrollFormCarousel(this, 'next')" type="button">
                            <span class="material-symbols-outlined">chevron_right</span>
                        </button>
                    </div>
                </div>

                \2'''
content = apply_prog_pattern.sub(apply_prog_replacement, content, count=1)

# 3. Replace Recruit Step 1 Program Selection
recruit_prog_pattern = re.compile(r'(<!-- Program Selection Card -->\s*<div class="[^"]*rounded-xl p-6 md:p-8">).*?(<!-- Specialty Selection Card -->)', re.DOTALL)
recruit_prog_replacement = r'''\1
                    <h2 class="font-headline-sm text-headline-sm text-on-surface mb-stack-md flex items-center gap-2">
                        <span class="material-symbols-outlined text-primary" style="font-variation-settings: 'FILL' 1;">grid_view</span>
                        모집 프로그램 선택
                    </h2>
                    
                    <div class="mb-6">
                        <label class="block font-label-md text-label-md text-on-surface-variant mb-2">1단계: 대분류 카테고리 선택</label>
                        <select id="recruit-category-select" class="w-full bg-surface-container-low border border-outline-variant/50 rounded-lg px-4 py-3 font-body-md text-body-md focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all appearance-none cursor-pointer" onchange="filterPrograms('recruit')">
                            <option value="">카테고리를 선택하세요</option>
                        </select>
                    </div>

                    <div class="relative group px-12" id="recruit-program-container" style="display: none;">
                        <label class="block font-label-md text-label-md text-on-surface-variant mb-2 -ml-12">2단계: 상세 프로그램 선택</label>
                        <button class="absolute left-0 top-1/2 -translate-y-1/2 z-10 w-10 h-10 rounded-full bg-white shadow-lg border border-outline-variant/30 flex items-center justify-center text-primary hover:bg-surface-container transition-all md:opacity-0 md:group-hover:opacity-100 hidden md:flex" onclick="scrollFormCarousel(this, 'prev')" type="button">
                            <span class="material-symbols-outlined">chevron_left</span>
                        </button>
                        <div class="w-full overflow-hidden" id="recruit-carousel-wrapper">
                            <div class="carousel-container flex gap-4 pb-2 transition-transform duration-300 w-max" id="recruit-program-carousel-track">
                            </div>
                        </div>
                        <button class="absolute right-0 top-1/2 -translate-y-1/2 z-10 w-10 h-10 rounded-full bg-white shadow-lg border border-outline-variant/30 flex items-center justify-center text-primary hover:bg-surface-container transition-all md:opacity-0 md:group-hover:opacity-100 hidden md:flex" onclick="scrollFormCarousel(this, 'next')" type="button">
                            <span class="material-symbols-outlined">chevron_right</span>
                        </button>
                    </div>
                </div>
                
                \2'''
content = recruit_prog_pattern.sub(recruit_prog_replacement, content, count=1)

# 4. Replace Keycard page with Discord Auth
keycard_pattern = re.compile(r'(<div id="page-keycard" class="page">).*?(<!-- ============================== -->\s*<!-- 화면명: 멤버 모집 1단계)', re.DOTALL)
keycard_replacement = r'''\1
        <div class="flex items-center justify-center min-h-[70vh] relative z-10 w-full">
            <div class="max-w-2xl w-full">
                <div class="glass-card rounded-xl shadow-[0px_4px_20px_rgba(0,0,0,0.05)] p-8 md:p-12 flex flex-col items-center text-center">
                    <div class="w-20 h-20 rounded-full bg-surface-container-high flex items-center justify-center mb-6 shadow-sm border border-surface-container-highest">
                        <span class="material-symbols-outlined text-primary text-4xl" style="font-variation-settings: 'FILL' 1;">how_to_reg</span>
                    </div>
                    <h2 class="font-headline-lg text-headline-lg text-on-surface mb-2">신청 완료 및 디스코드 인증</h2>
                    <p class="font-body-lg text-body-lg text-on-surface-variant mb-8 max-w-md">
                        신청 내역이 안전하게 기록되었습니다.<br>팀 소통을 위해 본인의 <strong>웹 로그인 아이디</strong>를 입력하고 인증을 완료해주세요.
                    </p>
                    
                    <div class="w-full max-w-sm mb-8 space-y-4 text-left">
                        <div>
                            <label class="block font-label-md text-label-md text-on-surface-variant mb-1 ml-1">나의 아이디 (ID) 확인</label>
                            <input type="text" id="discord-auth-id" class="w-full bg-surface-container-lowest border border-primary/50 rounded-xl px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-primary transition-all text-center" placeholder="현재 로그인한 아이디를 입력하세요">
                        </div>
                    </div>

                    <div class="flex flex-col sm:flex-row gap-4 w-full max-w-md">
                        <button onclick="navigate('dashboard')" class="flex-1 py-4 px-6 rounded-xl border border-outline-variant/50 text-on-surface-variant font-headline-sm hover:bg-surface-container transition-all active:scale-95">
                            나중에 하기
                        </button>
                        <button onclick="submitDiscordAuth()" class="flex-1 py-4 px-6 rounded-xl bg-discord text-white font-headline-sm shadow-md shadow-discord/20 hover:shadow-lg hover:-translate-y-0.5 transition-all flex justify-center items-center gap-2" style="background-color: #5865F2;">
                            <span class="material-symbols-outlined text-[20px]">verified</span>
                            디스코드 계정 인증
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    \2'''
content = keycard_pattern.sub(keycard_replacement, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('UI Markup Replacements Done!')
