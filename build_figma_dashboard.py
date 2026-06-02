import re

def update_dashboard():
    current_html_path = 'web/index.html'
    
    with open(current_html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    dash_start = content.find('<div id="page-dashboard" class="page">')
    if dash_start == -1:
        print("Could not find page-dashboard")
        return
        
    next_page_start = content.find('<div id="page-apply-step1"', dash_start)
    dash_end = content.rfind('<!--', dash_start, next_page_start)
    if dash_end == -1:
        dash_end = next_page_start

    new_dashboard = """<div id="page-dashboard" class="page">
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start pb-12">
            
            <!-- Main Content (Left) -->
            <div class="lg:col-span-9 space-y-10">
                <!-- Section 1 -->
                <div>
                    <div class="flex items-center justify-between mb-4">
                        <h2 class="font-headline-sm text-on-surface flex items-center gap-2">가장 활발한 프로그램 목록 <span class="material-symbols-outlined text-[18px]">local_fire_department</span></h2>
                        <button class="text-label-sm text-on-surface-variant hover:text-primary">View all</button>
                    </div>
                    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                        <div class="glass-card rounded-xl overflow-hidden border border-outline-variant/30 bg-white hover:-translate-y-1 transition-transform cursor-pointer shadow-sm">
                            <div class="h-28 bg-surface-container-high relative">
                                <span class="absolute top-2 left-2 bg-[#ff5252] text-white text-[10px] px-2 py-0.5 rounded-full font-bold">Hot</span>
                            </div>
                            <div class="p-4 space-y-2">
                                <h3 class="font-headline-sm text-[15px] text-on-surface">실무 역량 강화 해커톤</h3>
                                <p class="text-[12px] text-on-surface-variant line-clamp-2 leading-tight">2024 동계 학술 팀 프로젝트 참여자를 모집합니다.</p>
                                <div class="flex items-center text-[11px] text-on-surface-variant pt-2">
                                    <span class="material-symbols-outlined text-[14px] mr-1">schedule</span> D-3 left
                                </div>
                            </div>
                        </div>
                        <div class="glass-card rounded-xl overflow-hidden border border-outline-variant/30 bg-surface-container-lowest hover:-translate-y-1 transition-transform cursor-pointer shadow-sm flex flex-col">
                            <div class="h-28 flex items-center justify-center bg-blue-50/30 text-on-surface-variant">
                                <span class="material-symbols-outlined text-[32px]">rocket_launch</span>
                            </div>
                            <div class="p-4 space-y-2 flex-grow">
                                <h3 class="font-headline-sm text-[15px] text-on-surface">글로벌 리더십 포럼</h3>
                                <p class="text-[12px] text-on-surface-variant line-clamp-2 leading-tight">해외 인턴십 연계 우수 프로그램</p>
                                <div class="flex items-center text-[11px] text-on-surface-variant pt-2">
                                    <span class="material-symbols-outlined text-[14px] mr-1">person</span> 12/20 Joined
                                </div>
                            </div>
                        </div>
                        <div class="glass-card rounded-xl overflow-hidden border border-outline-variant/30 bg-surface-container-lowest hover:-translate-y-1 transition-transform cursor-pointer shadow-sm flex flex-col">
                            <div class="h-28 flex items-center justify-center bg-blue-50/30 text-on-surface-variant">
                                <span class="material-symbols-outlined text-[32px]">emoji_events</span>
                            </div>
                            <div class="p-4 space-y-2 flex-grow">
                                <h3 class="font-headline-sm text-[15px] text-on-surface">창업 경진대회 2024</h3>
                                <p class="text-[12px] text-on-surface-variant line-clamp-2 leading-tight">아이디어를 현실로 바꾸는 기회</p>
                                <div class="flex items-center text-[11px] text-on-surface-variant pt-2">
                                    <span class="material-symbols-outlined text-[14px] mr-1">schedule</span> Ending today
                                </div>
                            </div>
                        </div>
                        <div class="glass-card rounded-xl overflow-hidden border border-outline-variant/30 bg-surface-container-lowest hover:-translate-y-1 transition-transform cursor-pointer shadow-sm flex flex-col">
                            <div class="h-28 flex items-center justify-center bg-blue-50/30 text-on-surface-variant">
                                <span class="material-symbols-outlined text-[32px]">school</span>
                            </div>
                            <div class="p-4 space-y-2 flex-grow">
                                <h3 class="font-headline-sm text-[15px] text-on-surface">전공 심화 스터디</h3>
                                <p class="text-[12px] text-on-surface-variant line-clamp-2 leading-tight">우수 멘토와 함께하는 학습 소모임</p>
                                <div class="flex items-center text-[11px] text-on-surface-variant pt-2">
                                    <span class="material-symbols-outlined text-[14px] mr-1">group</span> 5 slots open
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Section 2 -->
                <div>
                    <div class="flex items-center justify-between mb-4">
                        <h2 class="font-headline-sm text-on-surface">디자인 관련 프로그램</h2>
                    </div>
                    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                        <div class="glass-card rounded-xl overflow-hidden border border-outline-variant/30 bg-white hover:-translate-y-1 transition-transform cursor-pointer shadow-sm flex flex-col">
                            <div class="h-28 flex items-center justify-center bg-pink-50/30 text-[#8e4a5d]">
                                <span class="material-symbols-outlined text-[32px]">palette</span>
                            </div>
                            <div class="p-4 space-y-2 flex-grow">
                                <h3 class="font-headline-sm text-[15px] text-on-surface">UI/UX 마스터 클래스</h3>
                                <p class="text-[12px] text-on-surface-variant">Design Track</p>
                            </div>
                        </div>
                        <div class="glass-card rounded-xl overflow-hidden border border-outline-variant/30 bg-white hover:-translate-y-1 transition-transform cursor-pointer shadow-sm flex flex-col">
                            <div class="h-28 flex items-center justify-center bg-pink-50/30 text-[#8e4a5d]">
                                <span class="material-symbols-outlined text-[32px]">auto_fix_high</span>
                            </div>
                            <div class="p-4 space-y-2 flex-grow">
                                <h3 class="font-headline-sm text-[15px] text-on-surface">3D 그래픽 입문</h3>
                                <p class="text-[12px] text-on-surface-variant">Modeling</p>
                            </div>
                        </div>
                        <div class="glass-card rounded-xl overflow-hidden border border-outline-variant/30 bg-white hover:-translate-y-1 transition-transform cursor-pointer shadow-sm flex flex-col">
                            <div class="h-28 flex items-center justify-center bg-pink-50/30 text-[#8e4a5d]">
                                <span class="material-symbols-outlined text-[32px]">architecture</span>
                            </div>
                            <div class="p-4 space-y-2 flex-grow">
                                <h3 class="font-headline-sm text-[15px] text-on-surface">타이포그래피 워크숍</h3>
                                <p class="text-[12px] text-on-surface-variant">Font Design</p>
                            </div>
                        </div>
                        <div class="glass-card rounded-xl overflow-hidden border border-outline-variant/30 bg-white hover:-translate-y-1 transition-transform cursor-pointer shadow-sm flex flex-col">
                            <div class="h-28 flex items-center justify-center bg-pink-50/30 text-[#8e4a5d]">
                                <span class="material-symbols-outlined text-[32px]">brush</span>
                            </div>
                            <div class="p-4 space-y-2 flex-grow">
                                <h3 class="font-headline-sm text-[15px] text-on-surface">디지털 일러스트레이션</h3>
                                <p class="text-[12px] text-on-surface-variant">Digital Art</p>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Section 3 -->
                <div>
                    <div class="flex items-center justify-between mb-4">
                        <h2 class="font-headline-sm text-on-surface">AI 관련 프로그램</h2>
                    </div>
                    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                        <div class="glass-card rounded-xl overflow-hidden border border-outline-variant/30 bg-white hover:-translate-y-1 transition-transform cursor-pointer shadow-sm">
                            <div class="p-4 space-y-2">
                                <div class="w-8 h-8 flex items-center justify-center text-on-surface-variant mb-2">
                                    <span class="material-symbols-outlined">psychology</span>
                                </div>
                                <h3 class="font-headline-sm text-[15px] text-on-surface">LLM 활용 기초</h3>
                                <p class="text-[12px] text-on-surface-variant line-clamp-2">ChatGPT API를 활용한 서비스 개발 기초 과정입니다.</p>
                            </div>
                        </div>
                        <div class="glass-card rounded-xl overflow-hidden border border-outline-variant/30 bg-white hover:-translate-y-1 transition-transform cursor-pointer shadow-sm">
                            <div class="p-4 space-y-2">
                                <div class="w-8 h-8 flex items-center justify-center text-on-surface-variant mb-2">
                                    <span class="material-symbols-outlined">smart_toy</span>
                                </div>
                                <h3 class="font-headline-sm text-[15px] text-on-surface">AI 챗봇 개발</h3>
                                <p class="text-[12px] text-on-surface-variant line-clamp-2">나만의 커스텀 AI 비서를 직접 만들어보는 실습 과정입니다.</p>
                            </div>
                        </div>
                        <div class="glass-card rounded-xl overflow-hidden border border-outline-variant/30 bg-white hover:-translate-y-1 transition-transform cursor-pointer shadow-sm">
                            <div class="p-4 space-y-2">
                                <div class="w-8 h-8 flex items-center justify-center text-on-surface-variant mb-2">
                                    <span class="material-symbols-outlined">analytics</span>
                                </div>
                                <h3 class="font-headline-sm text-[15px] text-on-surface">데이터 분석가 캠프</h3>
                                <p class="text-[12px] text-on-surface-variant line-clamp-2">Python과 머신러닝을 활용한 데이터 인사이트 도출 학습</p>
                            </div>
                        </div>
                        <div class="glass-card rounded-xl overflow-hidden border border-outline-variant/30 bg-white hover:-translate-y-1 transition-transform cursor-pointer shadow-sm">
                            <div class="p-4 space-y-2">
                                <div class="w-8 h-8 flex items-center justify-center text-on-surface-variant mb-2">
                                    <span class="material-symbols-outlined">memory</span>
                                </div>
                                <h3 class="font-headline-sm text-[15px] text-on-surface">파이썬 머신러닝</h3>
                                <p class="text-[12px] text-on-surface-variant line-clamp-2">기초부터 심화까지 이어지는 인공지능 엔지니어 과정</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Sidebar (Right) -->
            <aside class="lg:col-span-3 space-y-6 lg:sticky lg:top-24">
                <!-- Profile Card -->
                <div class="glass-card rounded-xl p-6 shadow-sm border border-outline-variant/30 bg-white flex flex-col items-center">
                    <div class="flex items-center gap-4 w-full mb-6">
                        <div class="w-12 h-12 rounded-full bg-primary-container text-primary flex items-center justify-center shrink-0">
                            <span class="material-symbols-outlined">person</span>
                        </div>
                        <div>
                            <h3 class="font-headline-sm text-on-surface">김ㅁㅁ씨 환영합니다</h3>
                            <p class="text-[12px] text-on-surface-variant">DUS Member</p>
                        </div>
                    </div>
                    <div class="flex items-center justify-between w-full gap-2">
                        <button class="flex-1 py-2 text-[12px] border border-outline-variant rounded-full flex items-center justify-center gap-1 hover:bg-surface-container transition-colors" onclick="logout()">
                            <span class="material-symbols-outlined text-[14px]">logout</span> 로그아웃
                        </button>
                        <button class="flex-1 py-2 text-[12px] border border-outline-variant rounded-full flex items-center justify-center gap-1 hover:bg-surface-container transition-colors" onclick="navigate('profile')">
                            <span class="material-symbols-outlined text-[14px]">account_circle</span> 내정보
                        </button>
                        <button class="w-10 h-10 shrink-0 border border-outline-variant rounded-full flex items-center justify-center hover:bg-surface-container transition-colors">
                            <span class="material-symbols-outlined text-[16px]">notifications</span>
                        </button>
                    </div>
                </div>

                <!-- Apply Card -->
                <div class="glass-card rounded-xl p-6 shadow-sm border border-outline-variant/30 bg-white flex flex-col text-left">
                    <div class="flex items-center gap-3 mb-4">
                        <div class="w-10 h-10 rounded-full bg-surface-container-highest text-on-surface flex items-center justify-center shrink-0">
                            <span class="material-symbols-outlined text-[20px]" style="font-variation-settings: 'FILL' 1;">handshake</span>
                        </div>
                        <h3 class="font-headline-sm text-on-surface">매칭 신청</h3>
                    </div>
                    <p class="text-[13px] text-on-surface-variant mb-6 leading-relaxed">최적의 팀원을 찾아보세요. 현재 12개의 프로젝트가 당신의 전공 역량을 기다리고 있습니다.</p>
                    <button class="w-full py-3.5 rounded-xl bg-[#f5e6ff] text-[#8e4a5d] font-label-md font-bold hover:bg-[#ebd4f9] transition-colors" onclick="navigate('status')">
                        지금 매칭 신청하기
                    </button>
                </div>

                <!-- Discord Card -->
                <div class="glass-card rounded-xl p-6 shadow-sm border border-primary/20 bg-white">
                    <div class="flex items-center gap-2 mb-4 text-[#5865F2]">
                        <span class="material-symbols-outlined text-[24px]">forum</span>
                        <h3 class="font-headline-sm text-on-surface">팀 매칭 보드 (Discord)</h3>
                    </div>
                    <p class="text-[13px] text-on-surface-variant mb-6 leading-relaxed">실시간으로 팀원들과 소통하고 프로젝트 협업을 시작하세요.</p>
                    <button class="text-[#5865F2] font-label-md font-bold hover:underline flex items-center gap-1" onclick="openAuthModal()">
                        Discord 채널 입장하기 <span class="material-symbols-outlined text-[16px]">arrow_forward</span>
                    </button>
                </div>
            </aside>
            
        </div>
    </div>\n\n"""

    final_content = content[:dash_start] + new_dashboard + content[dash_end:]

    with open(current_html_path, 'w', encoding='utf-8') as f:
        f.write(final_content)
    print("Figma Dashboard successfully built and applied!")

if __name__ == '__main__':
    update_dashboard()
