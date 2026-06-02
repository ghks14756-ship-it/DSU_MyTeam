import re

def fix_html():
    with open('web/index.html', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Find the start of the left-over "Left Column: Status Card"
    start_idx = -1
    for i, line in enumerate(lines):
        if "<!-- Left Column: Status Card (Prominent) -->" in line:
            start_idx = i
            break

    # Find the end of the left-over block
    end_idx = -1
    if start_idx != -1:
        for i in range(start_idx, len(lines)):
            if "</section>" in lines[i] and i > start_idx + 20:
                # Need to also skip the </div> </div> right after it
                end_idx = i + 2
                break

    print(f"Old block: {start_idx} to {end_idx}")

    # Now, find the static team cards in the new layout
    static_start = -1
    for i, line in enumerate(lines):
        if '<div class="grid grid-cols-1 gap-6" id="team-list-container-static">' in line:
            static_start = i - 1 # Include the comment above it
            break

    static_end = -1
    if static_start != -1:
        for i in range(static_start + 2, len(lines)):
            if "</div>" in lines[i]:
                # find the closing div of the grid
                # The static block has 3 cards, each card is a div
                # We can just look for the first </section> after static_start, then go back 1 div
                pass

    # A better way is to use regex or string replace for the specific blocks.
    with open('web/index.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Replace the buttons with select filter and dynamic container
    old_middle_header = '''                    <div class="flex gap-2 bg-white rounded-full p-1 border border-outline-variant/30 shadow-sm">
                        <button class="px-4 py-1.5 rounded-full text-[13px] text-on-surface bg-surface-container-low font-bold">최신순</button>
                        <button class="px-4 py-1.5 rounded-full text-[13px] text-on-surface-variant hover:bg-surface-container-low transition-colors">인기순</button>
                    </div>
                </div>'''
    
    new_middle_header = '''                    <div class="flex gap-2 relative">
                        <select id="team-sort-filter" class="appearance-none flex items-center gap-2 pl-10 pr-8 py-2 border border-outline-variant text-on-surface-variant rounded-lg font-label-md text-label-md hover:bg-surface-container transition-colors cursor-pointer bg-transparent" onchange="sortAndRenderTeams()">
                            <option value="none">필터 (기본)</option>
                            <option value="program_asc">대제목 오름차순 (가나다순)</option>
                            <option value="program_desc">대제목 내림차순 (역순)</option>
                            <option value="members_asc">인원수 오름차순</option>
                            <option value="members_desc">인원수 내림차순</option>
                        </select>
                        <span class="material-symbols-outlined text-[20px] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none text-on-surface-variant">filter_list</span>
                        <span class="material-symbols-outlined text-[20px] absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-on-surface-variant">expand_more</span>
                    </div>
                </div>'''
    
    content = content.replace(old_middle_header, new_middle_header)

    # 2. Remove the static team cards completely, and replace with dynamic container
    # Since we know it starts with '<!-- Static Team Cards based on Figma Design', we can use regex
    pattern = re.compile(r'<!-- Static Team Cards based on Figma Design.*?</div>\s*</section>', re.DOTALL)
    
    new_container = '''<div class="grid grid-cols-1 gap-4" id="team-list-container">
                    <!-- Dynamic team cards will be rendered here -->
                </div>
            </section>'''
    
    content = pattern.sub(new_container, content)

    # 3. Remove the entire bottom block that leaked out of page-status
    leak_pattern = re.compile(r'<!-- Left Column: Status Card \(Prominent\) -->.*?</section>\s*</div>\s*</div>', re.DOTALL)
    content = leak_pattern.sub('', content)

    with open('web/index.html', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    fix_html()
    print("Done")
