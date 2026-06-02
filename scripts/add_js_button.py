import re

with open('web/index.html', 'r', encoding='utf-8') as f:
    c = f.read()

btn_html = '<button type="button" class="opacity-0 group-hover:opacity-100 transition-opacity ml-1 w-4 h-4 flex items-center justify-center hover:text-error text-current" onclick="event.preventDefault(); this.closest(\\\'div\\\').remove();"><span class="material-symbols-outlined text-[14px]">close</span></button>'

# Inject into tagHtml (tech_stack)
c = re.sub(
    r'(const tagHtml\s*=\s*`<div class="group inline-block">.*?)\$\{val\}</span></div>`;',
    rf'\g<1>${{val}}{btn_html}</span></div>`;',
    c
)

# Inject into labelHtml (skill)
c = re.sub(
    r'(const labelHtml\s*=\s*`<div class="group inline-block">.*?)\$\{value\}</span></div>`;',
    rf'\g<1>${{value}}{btn_html}</span></div>`;',
    c
)

with open('web/index.html', 'w', encoding='utf-8') as f:
    f.write(c)
