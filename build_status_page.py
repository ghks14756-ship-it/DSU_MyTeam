import re

def build_status_page():
    current_html_path = 'web/index.html'
    
    with open(current_html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    status_start = content.find('<div id="page-status" class="page">')
    if status_start == -1:
        print("Could not find page-status")
        return
        
    status_end = content.find('<!--', status_start + 100)
    if status_end == -1:
        status_end = content.find('</script>', status_start)

    new_status_page = """<div id="page-status" class="page">
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start pb-12">
            
            <!-- Left Sidebar: Program Categories -->
            <aside class="lg:col-span-3 space-y-4">
                <div class="glass-card rounded-xl shadow-[0_4px_20px_rgba(0,0,0,0.05)] border border-outline-variant/30 bg-white overflow-hidden">
                    <h3 class="font-headline-sm text-on-surface px-6 py-5 border-b border-outline-variant/30 font-bold">프로그램 카테고리</h3>
                    <ul class="flex flex-col">
                        <li><button class="w-full px-6 py-4 flex justify-between items-center text-on-surface-variant hover:bg-surface-container-low transition-colors text-[14px]" onclick="filterTeams('all')">베스트 프로그램 <span class="material-symbols-outlined text-[16px]">chevron_right</span></button></li>
                        <li><button class="w-full px-6 py-4 flex justify-between items-center text-on-surface-variant hover:bg-surface-container-low transition-colors text-[14px]" onclick="filterTeams('design')">디자인 관련 프로그램 <span class="material-symbols-outlined text-[16px]">chevron_right</span></button></li>
                        <li><button class="w-full px-6 py-4 flex justify-between items-center text-on-surface-variant hover:bg-surface-container-low transition-colors text-[14px]" onclick="filterTeams('ai')">AI 관련 프로그램 <span class="material-symbols-outlined text-[16px]">chevron_right</span></button></li>
                        <li><button class="w-full px-6 py-4 flex justify-between items-center text-on-surface-variant hover:bg-surface-container-low transition-colors text-[14px]" onclick="filterTeams('humanities')">인문 문학 프로그램 <span class="material-symbols-outlined text-[16px]">chevron_right</span></button></li>
                    </ul>
                </div>
            </aside>

            <!-- Middle Column: Team List -->
            <section class="lg:col-span-6 space-y-6">
                <div class="flex items-center justify-between mb-2">
                    <h2 class="font-headline-md text-headline-md text-on-surface font-bold">매칭 대기 중인 팀</h2>
                    <div class="flex gap-2 bg-white rounded-full p-1 border border-outline-variant/30 shadow-sm">
                        <button class="px-4 py-1.5 rounded-full text-[13px] text-on-surface bg-surface-container-low font-bold">최신순</button>
                        <button class="px-4 py-1.5 rounded-full text-[13px] text-on-surface-variant hover:bg-surface-container-low transition-colors">인기순</button>
                    </div>
                </div>
                
                <!-- Static Team Cards based on Figma Design (JS dynamic render is overridden for this static layout to match exactly) -->
                <div class="grid grid-cols-1 gap-6" id="team-list-container">
                    <!-- Card 1 -->
                    <div class="glass-card rounded-xl p-6 shadow-[0_4px_20px_rgba(0,0,0,0.05)] border border-outline-variant/30 bg-white hover:-translate-y-1 transition-transform">
                        <div class="flex justify-between items-start mb-2">
                            <h3 class="font-headline-sm text-[18px] text-on-surface">Global Exchange Project</h3>
                            <span class="bg-[#fcefee] text-[#9c4d57] text-[11px] font-bold px-3 py-1 rounded-sm">모집 중 1/4</span>
                        </div>
                        <p class="text-[13px] text-on-surface-variant mb-4">팀장: Kim*min</p>
                        <div class="flex flex-wrap gap-2 mb-4">
                            <span class="bg-[#f3f4fb] text-[#4d5b9c] text-[11px] px-3 py-1 rounded-full">UI Design</span>
                            <span class="bg-[#f3f4fb] text-[#4d5b9c] text-[11px] px-3 py-1 rounded-full">English Speaker</span>
                        </div>
                        <p class="text-[13px] text-on-surface-variant leading-relaxed mb-6">글로벌 교환 학생들을 위한 문화 교류 플랫폼을 제작하고 있습니다. 창의적인 UI 디자이너와 원활한 소통이 가능한 팀원을 찾습니다.</p>
                        <div class="flex justify-end">
                            <button class="px-6 py-2.5 rounded-full bg-[#fcefee] text-[#9c4d57] font-label-md text-[13px] font-bold hover:bg-[#f6d7d5] transition-colors" onclick="navigate('apply-step1', {mode: 'join'})">참가 신청하기</button>
                        </div>
                    </div>

                    <!-- Card 2 -->
                    <div class="glass-card rounded-xl p-6 shadow-[0_4px_20px_rgba(0,0,0,0.05)] border border-outline-variant/30 bg-white hover:-translate-y-1 transition-transform">
                        <div class="flex justify-between items-start mb-2">
                            <h3 class="font-headline-sm text-[18px] text-on-surface">Startup Mentoring Program</h3>
                            <span class="bg-[#fcefee] text-[#9c4d57] text-[11px] font-bold px-3 py-1 rounded-sm">모집 중 3/4</span>
                        </div>
                        <p class="text-[13px] text-on-surface-variant mb-4">팀장: Lee*seo</p>
                        <div class="flex flex-wrap gap-2 mb-4">
                            <span class="bg-[#f3f4fb] text-[#4d5b9c] text-[11px] px-3 py-1 rounded-full">Web Dev</span>
                            <span class="bg-[#f3f4fb] text-[#4d5b9c] text-[11px] px-3 py-1 rounded-full">React</span>
                        </div>
                        <p class="text-[13px] text-on-surface-variant leading-relaxed mb-6">초기 스타트업을 위한 매칭 알고리즘을 고도화하고 있습니다. 프론트엔드 개발 경험이 있는 분들의 많은 지원 바랍니다.</p>
                        <div class="flex justify-end">
                            <button class="px-6 py-2.5 rounded-full bg-[#fcefee] text-[#9c4d57] font-label-md text-[13px] font-bold hover:bg-[#f6d7d5] transition-colors" onclick="navigate('apply-step1', {mode: 'join'})">참가 신청하기</button>
                        </div>
                    </div>

                    <!-- Card 3 -->
                    <div class="glass-card rounded-xl p-6 shadow-[0_4px_20px_rgba(0,0,0,0.05)] border border-outline-variant/30 bg-white hover:-translate-y-1 transition-transform">
                        <div class="flex justify-between items-start mb-2">
                            <h3 class="font-headline-sm text-[18px] text-on-surface">Campus Life Hack App</h3>
                            <span class="bg-[#fcefee] text-[#9c4d57] text-[11px] font-bold px-3 py-1 rounded-sm">모집 중 2/5</span>
                        </div>
                        <p class="text-[13px] text-on-surface-variant mb-4">팀장: Park*jun</p>
                        <div class="flex flex-wrap gap-2 mb-4">
                            <span class="bg-[#f3f4fb] text-[#4d5b9c] text-[11px] px-3 py-1 rounded-full">Product Management</span>
                            <span class="bg-[#f3f4fb] text-[#4d5b9c] text-[11px] px-3 py-1 rounded-full">Data Analysis</span>
                        </div>
                        <p class="text-[13px] text-on-surface-variant leading-relaxed mb-6">대학 생활의 불편함을 해소하는 앱 서비스 기획 단계입니다. 데이터 분석에 기반한 서비스 성장을 함께 고민할 분을 찾습니다.</p>
                        <div class="flex justify-end">
                            <button class="px-6 py-2.5 rounded-full bg-[#fcefee] text-[#9c4d57] font-label-md text-[13px] font-bold hover:bg-[#f6d7d5] transition-colors" onclick="navigate('apply-step1', {mode: 'join'})">참가 신청하기</button>
                        </div>
                    </div>
                </div>
            </section>

            <!-- Right Sidebar: Navigation Cards -->
            <aside class="lg:col-span-3 space-y-6 lg:sticky lg:top-24">
                <!-- Apply Card -->
                <div class="glass-card rounded-xl p-6 shadow-[0_4px_20px_rgba(0,0,0,0.05)] border border-outline-variant/30 bg-white flex flex-col items-center text-center">
                    <div class="w-14 h-14 rounded-full bg-[#f5e6ff] text-[#8e4a5d] flex items-center justify-center mb-6 shadow-sm">
                        <span class="material-symbols-outlined text-[28px]">groups</span>
                    </div>
                    <h3 class="font-headline-sm text-on-surface mb-3 font-bold text-[16px]">지금 바로 팀을 만들어보세요</h3>
                    <p class="text-[13px] text-on-surface-variant mb-8 leading-relaxed">나의 역량을 필요로 하는 최고의 팀원들을 만날 수 있습니다.</p>
                    <button class="w-full py-3.5 rounded-xl bg-[#f5e6ff] text-[#8e4a5d] font-label-md font-bold hover:bg-[#ebd4f9] transition-colors flex justify-center items-center gap-2" onclick="navigate('apply-step1')">
                        <span class="material-symbols-outlined text-[18px]">rocket_launch</span> 매칭 신청
                    </button>
                </div>
                
                <!-- Recruit Card -->
                <div class="glass-card rounded-xl p-6 shadow-[0_4px_20px_rgba(0,0,0,0.05)] border border-outline-variant/30 bg-white flex flex-col items-center text-center">
                    <div class="w-14 h-14 rounded-full bg-[#fcefee] text-[#9c4d57] flex items-center justify-center mb-6 shadow-sm">
                        <span class="material-symbols-outlined text-[28px]">contact_page</span>
                    </div>
                    <h3 class="font-headline-sm text-on-surface mb-3 font-bold text-[16px]">팀장을 맡아보세요</h3>
                    <p class="text-[13px] text-on-surface-variant mb-8 leading-relaxed">직접 프로젝트를 제안하고 비전을 함께 나눌 동료를 모집하세요.</p>
                    <button class="w-full py-3.5 rounded-xl bg-[#f3f4fb] text-[#4d5b9c] font-label-md font-bold hover:bg-[#e6e8f4] transition-colors flex justify-center items-center gap-2" onclick="navigate('recruit-step1')">
                        <span class="material-symbols-outlined text-[18px]">edit_document</span> 팀 등록
                    </button>
                </div>
            </aside>
            
        </div>
    </div>\n\n"""

    final_content = content[:status_start] + new_status_page + content[status_end:]

    # Also we need to disable the javascript renderTeams so it doesn't overwrite our static Figma cards.
    # We can just change `renderTeams()` or `sortAndRenderTeams()` to do nothing for now, or just leave it if it's called on load.
    # Actually, if sortAndRenderTeams is called, it overwrites innerHTML of team-list-container.
    # Let's change the ID of the container to `team-list-container-static` so JS doesn't overwrite it.
    final_content = final_content.replace('id="team-list-container"', 'id="team-list-container-static"')

    with open(current_html_path, 'w', encoding='utf-8') as f:
        f.write(final_content)
    print("Figma Status Page successfully built and applied!")

if __name__ == '__main__':
    build_status_page()
