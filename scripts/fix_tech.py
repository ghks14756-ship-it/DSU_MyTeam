with open('web/index.html', 'r', encoding='utf-8') as f:
    c = f.read()

js_func = '''    function addTechTag() {
        const inputEl = document.getElementById('input-tech-recruit');
        const container = document.getElementById('tech-tags-container');
        const wrapper = document.getElementById('wrapper-tech-recruit');
        if (inputEl && inputEl.value.trim() !== '' && container) {
            const val = inputEl.value.trim();
            const tagHtml = `<label class="cursor-pointer"><input name="tech_stack" value="${val}" checked class="peer sr-only" type="checkbox"><span class="inline-flex items-center gap-1 px-4 py-2 rounded-full border border-outline-variant/50 bg-surface-container-low font-label-md text-label-md text-on-surface-variant peer-checked:bg-primary peer-checked:text-on-primary peer-checked:border-primary transition-all">${val}</span></label>`;
            const btn = container.querySelector('button');
            if (btn) {
                btn.insertAdjacentHTML('beforebegin', tagHtml);
            } else {
                container.insertAdjacentHTML('beforeend', tagHtml);
            }
            inputEl.value = '';
            if(wrapper) wrapper.classList.add('hidden');
        }
    }'''

if 'function addTechTag' not in c:
    c = c.replace('function addCustomSkill', js_func + '\n\n    function addCustomSkill')

with open('web/index.html', 'w', encoding='utf-8') as f:
    f.write(c)
