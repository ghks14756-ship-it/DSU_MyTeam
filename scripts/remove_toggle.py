import re

with open('web/index.html', 'r', encoding='utf-8') as f:
    c = f.read()

def replace_tag(match):
    inner = match.group(1)
    
    # Change input type to hidden
    inner = re.sub(r'type="checkbox"', 'type="hidden"', inner)
    inner = re.sub(r'type=\\"checkbox\\"', r'type=\\"hidden\\"', inner)
    
    # Remove sr-only and peer classes from input
    inner = re.sub(r'class="peer sr-only"', '', inner)
    inner = re.sub(r'class=\\"peer sr-only\\"', '', inner)
    
    # Update span classes to be permanently active
    inner = re.sub(
        r'bg-surface-container-low font-label-md text-label-md text-on-surface-variant peer-checked:bg-primary peer-checked:text-on-primary peer-checked:border-primary',
        r'bg-primary font-label-md text-label-md text-on-primary border-primary',
        inner
    )
    
    # Replace the label's closest('label') in the X button onclick to closest('div')
    inner = inner.replace("closest('label')", "closest('div')")
    inner = inner.replace("closest(\\'label\\')", "closest(\\'div\\')")
    
    return f'<div class="group inline-block">{inner}</div>'

# For statically defined tags and JS templates
c = re.sub(r'<label class="cursor-pointer group">(\s*<input[^>]*name="[^"]*(?:skill|tech_stack)"[^>]*>.*?)</label>', replace_tag, c, flags=re.DOTALL)

with open('web/index.html', 'w', encoding='utf-8') as f:
    f.write(c)
