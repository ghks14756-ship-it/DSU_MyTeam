import re

with open('web/index.html', 'r', encoding='utf-8') as f:
    c = f.read()

# Add group class to labels that contain peer sr-only checkbox for skills
c = re.sub(r'<label class="cursor-pointer">(\s*<input[^>]*name="(?:skill|recruit_skill|tech_stack)"[^>]*>)', r'<label class="cursor-pointer group">\g<1>', c)

# Replace inline-block with inline-flex and append X button to spans
def replace_span(match):
    span_start = match.group(1)
    span_start = span_start.replace('inline-block', 'inline-flex items-center gap-1').replace('px-5', 'px-4')
    content = match.group(2)
    x_btn = '<button type="button" class="opacity-0 group-hover:opacity-100 transition-opacity ml-1 w-4 h-4 flex items-center justify-center hover:text-error text-current" onclick="event.preventDefault(); this.closest(\'label\').remove();"><span class="material-symbols-outlined text-[14px]">close</span></button>'
    return f"{span_start}{content}{x_btn}</span>"

c = re.sub(r'(<span[^>]*class="[^"]*inline-block[^"]*border[^"]*">)([^<]+)</span>', replace_span, c)

# Update JS functions
c = re.sub(
    r'(const labelHtml\s*=\s*`<label class="cursor-pointer"><input[^>]+><span[^>]+>)\$\{value\}</span></label>`;',
    r'\g<1>${value}<button type="button" class="opacity-0 group-hover:opacity-100 transition-opacity ml-1 w-4 h-4 flex items-center justify-center hover:text-error text-current" onclick="event.preventDefault(); this.closest(\'label\').remove();"><span class="material-symbols-outlined text-[14px]">close</span></button></span></label>`;',
    c
)

c = re.sub(
    r'(const labelHtml\s*=\s*`<label class="cursor-pointer"><input[^>]+><span[^>]+>)\$\{val\}</span></label>`;',
    r'\g<1>${val}<button type="button" class="opacity-0 group-hover:opacity-100 transition-opacity ml-1 w-4 h-4 flex items-center justify-center hover:text-error text-current" onclick="event.preventDefault(); this.closest(\'label\').remove();"><span class="material-symbols-outlined text-[14px]">close</span></button></span></label>`;',
    c
)

# Because we added "group" class statically, we must also add it to JS templates:
c = c.replace('<label class="cursor-pointer"><input name="skill"', '<label class="cursor-pointer group"><input name="skill"')
c = c.replace('<label class="cursor-pointer"><input name="tech_stack"', '<label class="cursor-pointer group"><input name="tech_stack"')

with open('web/index.html', 'w', encoding='utf-8') as f:
    f.write(c)
