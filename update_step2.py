import re

def update_dashboard():
    with open('web/index.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # The empty template to replace the 12 cards
    card_template = """                        <div class="glass-card rounded-xl overflow-hidden border border-outline-variant/30 bg-white hover:-translate-y-1 transition-transform cursor-pointer shadow-sm flex flex-col program-card-template" style="display: none;" onclick="navigate('apply-step1')">
                            <div class="h-28 flex items-center justify-center bg-surface-container-high text-primary relative card-thumbnail">
                                <span class="material-symbols-outlined text-[32px] card-icon">local_fire_department</span>
                            </div>
                            <div class="p-4 flex flex-col flex-grow">
                                <h3 class="font-headline-sm text-[15px] text-on-surface line-clamp-1 mb-2 card-title"></h3>
                                <p class="text-[12px] text-on-surface-variant line-clamp-2 leading-tight mb-4 flex-grow card-desc"></p>
                                <div class="flex items-center text-[11px] text-on-surface-variant pt-2 mt-auto border-t border-outline-variant/20 card-meta">
                                </div>
                            </div>
                        </div>"""

    # We need to find the three sections and replace their contents.
    # Let's locate Section 1, Section 2, Section 3
    
    # Section 1
    sec1_start = content.find('<!-- Section 1 -->')
    sec1_grid_start = content.find('<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">', sec1_start)
    if sec1_grid_start != -1:
        # replace with id="category-hot"
        content = content[:sec1_grid_start] + '<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4" id="category-hot">\n' + \
                  (card_template + '\n') * 4 + \
                  '                    </div>' + content[content.find('</div>', content.find('</div>', content.find('</div>', content.find('</div>', sec1_grid_start + 60)+6)+6)+6) + 6:]
                  # This is tricky using slicing. Let's use regex instead.

    return content

def safe_replace():
    with open('web/index.html', 'r', encoding='utf-8') as f:
        html = f.read()

    card_template = """                        <div class="glass-card rounded-xl overflow-hidden border border-outline-variant/30 bg-white hover:-translate-y-1 transition-transform cursor-pointer shadow-sm flex flex-col program-card-empty" style="opacity: 0.5;">
                            <div class="h-28 flex items-center justify-center bg-surface-container-high text-primary relative">
                                <span class="material-symbols-outlined text-[32px] card-icon">hourglass_empty</span>
                            </div>
                            <div class="p-4 flex flex-col flex-grow">
                                <h3 class="font-headline-sm text-[15px] text-on-surface line-clamp-1 mb-2 card-title">Loading...</h3>
                                <p class="text-[12px] text-on-surface-variant line-clamp-2 leading-tight mb-4 flex-grow card-desc">데이터를 불러오는 중입니다.</p>
                                <div class="flex items-center text-[11px] text-on-surface-variant pt-2 mt-auto border-t border-outline-variant/20 card-meta">
                                </div>
                            </div>
                        </div>"""

    # Replace Section 1 grid
    s1_pat = r'(<!-- Section 1 -->.*?<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4)(">.*?)(?=<!-- Section 2 -->)'
    html = re.sub(s1_pat, r'\1" id="category-hot">\n' + (card_template + '\n') * 4 + r'                    </div>\n                </div>\n                \n                ', html, flags=re.DOTALL)

    # Replace Section 2 grid
    s2_pat = r'(<!-- Section 2 -->.*?<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4)(">.*?)(?=<!-- Section 3 -->)'
    html = re.sub(s2_pat, r'\1" id="category-design">\n' + (card_template + '\n') * 4 + r'                    </div>\n                </div>\n\n                ', html, flags=re.DOTALL)

    # Replace Section 3 grid
    s3_pat = r'(<!-- Section 3 -->.*?<div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4)(">.*?)(?=</div>\n\n            <!-- Sidebar \(Right\) -->)'
    html = re.sub(s3_pat, r'\1" id="category-ai">\n' + (card_template + '\n') * 4 + r'                    </div>\n                </div>\n            ', html, flags=re.DOTALL)


    # Add JS script to fetch and map
    js_logic = """
    // --- Step 2: Dashboard Programs Fetch & Binding ---
    async function loadDashboardPrograms() {
        try {
            const res = await fetch('/api/activities');
            if (!res.ok) return;
            const data = await res.json();
            
            // Group by category
            const categories = {
                '가장 활발한 프로그램': document.getElementById('category-hot'),
                '디자인 관련': document.getElementById('category-design'),
                'AI 관련': document.getElementById('category-ai')
            };
            
            // Reset trackers
            const counts = { '가장 활발한 프로그램': 0, '디자인 관련': 0, 'AI 관련': 0 };
            
            data.forEach(item => {
                const cat = item['카테고리별 분류'];
                if (categories[cat] && counts[cat] < 4) {
                    const container = categories[cat];
                    const card = container.children[counts[cat]];
                    
                    // Remove empty state styling
                    card.classList.remove('program-card-empty');
                    card.style.opacity = '1';
                    card.setAttribute('onclick', "navigate('apply-step1', {mode: 'join'})");
                    
                    // Bind data
                    card.querySelector('.card-title').innerText = item.name || '제목 없음';
                    card.querySelector('.card-desc').innerText = item['전달사항'] || '상세 내용이 없습니다.';
                    
                    let metaText = '';
                    if (item.deadline) metaText += `<span class="material-symbols-outlined text-[14px] mr-1">schedule</span> ${item.deadline}`;
                    card.querySelector('.card-meta').innerHTML = metaText;
                    
                    // Set icons based on category
                    const iconEl = card.querySelector('.card-icon');
                    if (cat === '가장 활발한 프로그램') iconEl.innerText = 'local_fire_department';
                    else if (cat === '디자인 관련') iconEl.innerText = 'palette';
                    else if (cat === 'AI 관련') iconEl.innerText = 'psychology';
                    
                    counts[cat]++;
                }
            });
            
            // Optionally hide unused cards
            for (const cat in counts) {
                const container = categories[cat];
                for (let i = counts[cat]; i < 4; i++) {
                    container.children[i].style.display = 'none';
                }
            }
            
        } catch (e) {
            console.error("Dashboard load error:", e);
        }
    }
    
    // Call it on DOMContentLoaded
    document.addEventListener('DOMContentLoaded', () => {
        loadDashboardPrograms();
    });
"""
    if "loadDashboardPrograms()" not in html:
        html = html.replace('// Update Desktop Nav Active State', js_logic + '\n        // Update Desktop Nav Active State')

    with open('web/index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Done")

if __name__ == '__main__':
    safe_replace()
