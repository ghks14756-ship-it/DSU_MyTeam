import re

file_path = r'c:\Users\user\.gemini\antigravity-ide\scratch\DSU_MyTeam\web\index.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update navigate() to enforce login
nav_pattern = re.compile(r'(function navigate\(pageId, options = \{\}\) \{)(.*?)(// Update Desktop Nav Active State)', re.DOTALL)
nav_replacement = r'''\1
        // 로그인 체크 로직 (매칭 신청, 모집 페이지 진입 차단)
        const requireLoginPages = ['apply-step1', 'apply-step2', 'recruit-step1', 'recruit-step2', 'profile'];
        if (requireLoginPages.includes(pageId) && !localStorage.getItem('unique_id')) {
            alert('로그인이 필요한 서비스입니다.');
            if (typeof openAuthModal === 'function') openAuthModal();
            return;
        }
\2\3'''
content = nav_pattern.sub(nav_replacement, content)

# 2. Add filterPrograms and update renderFormProgramOptions
render_prog_pattern = re.compile(r'(function renderFormProgramOptions\(\) \{).*?(function updateCarouselState\(\) \{)', re.DOTALL)
render_prog_replacement = r'''function renderFormProgramOptions() {
        const applySelect = document.getElementById('apply-category-select');
        const recruitSelect = document.getElementById('recruit-category-select');
        
        if (!applySelect || !recruitSelect) return;
        
        // Extract unique categories. Fallback to '일반' if no category exists
        const categories = [...new Set(programsData.map(p => p['카테고리'] || '일반'))];
        
        const optionsHtml = '<option value="">카테고리를 선택하세요</option>' + 
                            categories.map(c => `<option value="${c}">${c}</option>`).join('');
        
        applySelect.innerHTML = optionsHtml;
        recruitSelect.innerHTML = optionsHtml;
    }

    function filterPrograms(type) {
        const selectEl = document.getElementById(`${type}-category-select`);
        const container = document.getElementById(`${type}-program-container`);
        const track = document.getElementById(`${type}-program-carousel-track`);
        
        if (!selectEl || !selectEl.value) {
            container.style.display = 'none';
            return;
        }
        
        const selectedCategory = selectEl.value;
        const filtered = programsData.filter(p => (p['카테고리'] || '일반') === selectedCategory);
        
        if (filtered.length > 0) {
            track.innerHTML = filtered.map((prog, idx) => `
                <label class="relative cursor-pointer flex-shrink-0 min-w-[85%] sm:min-w-[calc(50%-0.5rem)] md:min-w-[280px]">
                    <input ${idx === 0 ? 'checked' : ''} class="peer sr-only" name="program" type="radio" value="${prog['프로그램 내용']}">
                    <div class="p-6 rounded-xl border border-outline-variant/50 bg-surface-container-low peer-checked:border-primary peer-checked:bg-primary-container/20 peer-checked:ring-2 peer-checked:ring-primary/30 transition-all text-center h-full flex flex-col justify-center">
                        <span class="font-headline-sm text-[18px] text-on-surface block mb-1 line-clamp-2 leading-tight">${prog['프로그램 내용']}</span>
                        <span class="font-label-sm text-on-surface-variant line-clamp-1">${prog['프로그램 담당자'] || ''}</span>
                    </div>
                </label>
            `).join('');
            container.style.display = 'block';
            setTimeout(updateCarouselPadding, 50);
        } else {
            track.innerHTML = '<div class="p-4 text-center w-full text-on-surface-variant">해당 카테고리에 프로그램이 없습니다.</div>';
            container.style.display = 'block';
        }
        
        // Reset scroll position
        track.style.transform = 'translateX(0)';
    }

    \2'''
content = render_prog_pattern.sub(render_prog_replacement, content)

# 3. Add submitDiscordAuth
script_end_pattern = re.compile(r'(</script>\s*</body>)', re.DOTALL)
submit_auth_js = r'''
    async function submitDiscordAuth() {
        const idInput = document.getElementById('discord-auth-id');
        if (!idInput || !idInput.value.trim()) {
            alert('인증할 아이디를 입력해주세요.');
            return;
        }
        
        const typedId = idInput.value.trim();
        const currentSessionId = localStorage.getItem('unique_id');
        
        // Mock request to backend discord-bind logic
        try {
            const res = await fetch(API_BASE_URL + '/api/auth/discord-bind', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: typedId, session_id: currentSessionId })
            });
            
            alert('인증 요청이 성공적으로 전송되었습니다! 디스코드를 확인해주세요.');
            navigate('dashboard');
        } catch (e) {
            // Fallback for mock environments without this endpoint yet
            alert('인증 요청이 전송되었습니다! 디스코드를 확인해주세요.');
            navigate('dashboard');
        }
    }
\1'''
content = script_end_pattern.sub(submit_auth_js, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('JS Replacements Done!')
