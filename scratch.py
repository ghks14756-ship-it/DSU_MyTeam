import re

filepath = r'c:\Users\PC-1\.gemini\antigravity\scratch\DSU_MyTeam\web\index.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

navigate_count = len(re.findall(r'function navigate\(', content))
domready_count = len(re.findall(r"document\.addEventListener\('DOMContentLoaded'", content))
mouseup_count = len(re.findall(r"document\.addEventListener\('mouseup'", content))
top_page_css = '.top-page.active' in content
top_page_html = 'id="page-profile" class="top-page' in content
dashboard_hardcoded = 'id="page-dashboard" class="page active"' in content

print('navigate functions:', navigate_count, '=> OK' if navigate_count == 1 else '=> FAIL: should be 1')
print('DOMContentLoaded:', domready_count, '=> OK' if domready_count == 1 else '=> FAIL: should be 1')
print('mouseup listener:', mouseup_count, '=> OK' if mouseup_count == 1 else '=> FAIL: should be 1')
print('top-page CSS:', top_page_css, '=> OK' if top_page_css else '=> FAIL')
print('profile is top-page HTML:', top_page_html, '=> OK' if top_page_html else '=> FAIL')
print('dashboard hardcoded active:', dashboard_hardcoded, '=> OK' if not dashboard_hardcoded else '=> FAIL: should be False')
