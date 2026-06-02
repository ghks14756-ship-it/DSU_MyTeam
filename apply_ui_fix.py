import re
import os

def update_ui():
    original_html_path = 'original_index.html'
    current_html_path = 'web/index.html'
    
    # 1. Read Original HTML (UTF-16 LE due to powershell redirect)
    try:
        with open(original_html_path, 'r', encoding='utf-16le') as f:
            original_content = f.read()
    except Exception as e:
        print(f"Error reading original_index.html: {e}")
        return

    # Find the end of page-dashboard by looking for the next page, which is page-apply-step1
    dash_start = original_content.find('<div id="page-dashboard"')
    if dash_start == -1:
        print("Could not find page-dashboard in original")
        return
        
    next_page_start = original_content.find('<div id="page-apply-step1"', dash_start)
    if next_page_start == -1:
        print("Could not find page-apply-step1 in original")
        return
        
    # The dashboard block ends just before the comments of apply-step1
    # Let's just find the last </div> before page-apply-step1
    # Actually, we can just look back from next_page_start for <!-- or <div
    dash_end = original_content.rfind('<!--', dash_start, next_page_start)
    if dash_end == -1:
        dash_end = next_page_start
        
    original_dash = original_content[dash_start:dash_end]
    
    # Update navigation in Dashboard to go to 'status' instead of 'apply-step1'
    original_dash = re.sub(r'onclick="navigate\(\'apply-step1\'\)"([^>]*>지금 매칭 신청하기)', r'onclick="navigate(\'status\')"\1', original_dash)

    # 2. Read Current HTML
    with open(current_html_path, 'r', encoding='utf-8') as f:
        current_content = f.read()

    # Find boundaries in current HTML
    c_dash_start = current_content.find('<div id="page-dashboard"')
    c_next_start = current_content.find('<div id="page-apply-step1"', c_dash_start)
    c_dash_end = current_content.rfind('<!--', c_dash_start, c_next_start)
    if c_dash_end == -1:
        c_dash_end = c_next_start

    # Replace Dashboard in Current HTML
    current_content = current_content[:c_dash_start] + original_dash + current_content[c_dash_end:]

    # 3. Modify page-status to be 3-column
    status_start_idx = current_content.find('<div id="page-status" class="page">')
    if status_start_idx == -1:
        print("Could not find page-status in current html")
        return
        
    status_end_idx = current_content.find('<!--', status_start_idx + 100) # find the next comment which is the next page
    if status_end_idx == -1:
        status_end_idx = current_content.find('</script>', status_start_idx)

    status_block = current_content[status_start_idx:status_end_idx]

    # Modify the grid classes
    status_block = status_block.replace('<aside class="lg:col-span-4', '<aside class="lg:col-span-3')
    status_block = status_block.replace('<section class="lg:col-span-8', '<section class="lg:col-span-6')

    right_aside_html = """
            <!-- Right Column: Navigation Cards -->
            <aside class="lg:col-span-3 space-y-6 lg:sticky lg:top-24">
                <!-- Apply Card -->
                <div class="glass-card rounded-xl p-6 shadow-[0_4px_20px_rgba(0,0,0,0.05)] border-l-4 border-l-primary bg-white">
                    <div class="mb-4">
                        <div class="w-12 h-12 rounded-full bg-primary-container text-primary flex items-center justify-center mb-4 shadow-sm">
                            <span class="material-symbols-outlined text-[24px]" style="font-variation-settings: 'FILL' 1;">person_add</span>
                        </div>
                        <h3 class="font-headline-sm text-on-surface mb-2">매칭 신청</h3>
                        <p class="text-[13px] text-on-surface-variant leading-relaxed">원하는 팀을 찾고 있나요? 매칭 신청을 통해 내게 꼭 맞는 팀을 추천받으세요.</p>
                    </div>
                    <button class="w-full py-3.5 rounded-xl bg-primary text-on-primary font-label-md shadow-md hover:bg-primary/90 transition-colors flex items-center justify-center gap-2 active:scale-95" onclick="navigate('apply-step1')">
                        매칭 신청
                        <span class="material-symbols-outlined text-[18px]">arrow_forward</span>
                    </button>
                </div>
                
                <!-- Recruit Card -->
                <div class="glass-card rounded-xl p-6 shadow-[0_4px_20px_rgba(0,0,0,0.05)] border-l-4 border-l-secondary bg-white">
                    <div class="mb-4">
                        <div class="w-12 h-12 rounded-full bg-secondary-container text-secondary flex items-center justify-center mb-4 shadow-sm">
                            <span class="material-symbols-outlined text-[24px]" style="font-variation-settings: 'FILL' 1;">group_add</span>
                        </div>
                        <h3 class="font-headline-sm text-on-surface mb-2">팀장을 맡아보세요</h3>
                        <p class="text-[13px] text-on-surface-variant leading-relaxed">진행 중인 프로젝트가 있나요? 새로운 팀원을 직접 모집해 보세요.</p>
                    </div>
                    <button class="w-full py-3.5 rounded-xl bg-secondary text-on-secondary font-label-md shadow-md hover:bg-secondary/90 transition-colors flex items-center justify-center gap-2 active:scale-95" onclick="navigate('recruit-step1')">
                        팀 등록
                        <span class="material-symbols-outlined text-[18px]">arrow_forward</span>
                    </button>
                </div>
            </aside>
        </div>
"""
    # Find </section>
    section_end = status_block.rfind('</section>')
    if section_end != -1:
        grid_close = status_block.find('</div>', section_end)
        if grid_close != -1:
            status_block = status_block[:grid_close] + right_aside_html + status_block[grid_close+6:]

    # Combine back
    final_content = current_content[:status_start_idx] + status_block + current_content[status_end_idx:]

    with open(current_html_path, 'w', encoding='utf-8') as f:
        f.write(final_content)
    print("UI successfully updated!")

if __name__ == '__main__':
    update_ui()
