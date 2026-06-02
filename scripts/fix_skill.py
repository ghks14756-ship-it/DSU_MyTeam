import re

with open('web/index.html', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('onclick="toggleOtherInput(\'input-skill-apply\')"'.replace('"', '"'), 'onclick="toggleOtherInput(\'wrapper-skill-apply\', \'input-skill-apply\')"')
c = c.replace('onclick="toggleOtherInput(\'input-skill-recruit\')"'.replace('"', '"'), 'onclick="toggleOtherInput(\'wrapper-skill-recruit\', \'input-skill-recruit\')"')

c = re.sub(
    r'(<p class="font-body-md text-body-md text-on-surface-variant mb-stack-md">.*?</p>\s*)<div class="flex flex-wrap gap-3">',
    r'\g<1><div id="container-skill-apply" class="flex flex-wrap gap-3">',
    c, count=1
)
c = re.sub(
    r'(<p class="font-body-md text-body-md text-on-surface-variant mb-stack-md">.*?</p>\s*)<div class="flex flex-wrap gap-3">',
    r'\g<1><div id="container-skill-recruit" class="flex flex-wrap gap-3">',
    c, count=1
)

c = re.sub(
    r'<input id="input-skill-apply" type="text" class="mt-4 w-full bg-surface-container-low border border-outline-variant/50 rounded-lg px-4 py-3 font-body-md text-body-md focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all hidden" placeholder="직접 전문 분야를 입력하세요">',
    '<div id="wrapper-skill-apply" class="flex gap-2 mt-4 hidden"><input id="input-skill-apply" type="text" class="flex-1 bg-surface-container-low border border-outline-variant/50 rounded-lg px-4 py-3 font-body-md text-body-md focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all" placeholder="직접 전문 분야를 입력하세요"><button type="button" class="px-4 py-3 rounded-lg bg-primary text-on-primary font-label-md shadow-sm hover:bg-primary/90 transition-colors whitespace-nowrap" onclick="addCustomSkill(\'input-skill-apply\', \'container-skill-apply\', \'wrapper-skill-apply\')">입력 완료</button></div>',
    c
)

c = re.sub(
    r'<input id="input-skill-recruit" type="text" class="mt-4 w-full bg-surface-container-low border border-outline-variant/50 rounded-lg px-4 py-3 font-body-md text-body-md focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all hidden" placeholder="직접 희망 분야를 입력하세요">',
    '<div id="wrapper-skill-recruit" class="flex gap-2 mt-4 hidden"><input id="input-skill-recruit" type="text" class="flex-1 bg-surface-container-low border border-outline-variant/50 rounded-lg px-4 py-3 font-body-md text-body-md focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all" placeholder="직접 희망 분야를 입력하세요"><button type="button" class="px-4 py-3 rounded-lg bg-primary text-on-primary font-label-md shadow-sm hover:bg-primary/90 transition-colors whitespace-nowrap" onclick="addCustomSkill(\'input-skill-recruit\', \'container-skill-recruit\', \'wrapper-skill-recruit\')">입력 완료</button></div>',
    c
)

js_func = '''    function addCustomSkill(inputId, containerId, wrapperId) {
        const inputEl = document.getElementById(inputId);
        const containerEl = document.getElementById(containerId);
        const wrapperEl = document.getElementById(wrapperId);
        if (inputEl && inputEl.value.trim() !== '' && containerEl) {
            const value = inputEl.value.trim();
            const labelHtml = `<label class="cursor-pointer"><input name="skill" value="${value}" checked class="peer sr-only" type="checkbox"><span class="inline-block px-5 py-2 rounded-full border border-outline-variant/50 bg-surface-container-low font-label-md text-label-md text-on-surface-variant peer-checked:bg-primary peer-checked:text-on-primary peer-checked:border-primary transition-all">${value}</span></label>`;
            containerEl.insertAdjacentHTML('beforeend', labelHtml);
            inputEl.value = '';
            if (wrapperEl) wrapperEl.classList.add('hidden');
        }
    }'''

if 'function addCustomSkill' not in c:
    c = c.replace('function toggleOtherInput', js_func + '\n\n    function toggleOtherInput')

with open('web/index.html', 'w', encoding='utf-8') as f:
    f.write(c)
