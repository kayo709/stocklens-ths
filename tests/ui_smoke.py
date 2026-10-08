"""Optional Chromium/Playwright UI smoke. Needs: pip install playwright + system Chromium.
Uses real project backend functions injected as an API mock because sandbox browsers
cannot reach localhost HTTP. HTTP paths are tested independently by unittest.
"""
from pathlib import Path
import json
import sys
from urllib.parse import urlparse, parse_qs
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from diagnostic import build_diagnosis,route_query,scenario_pe
from playwright.sync_api import sync_playwright
STATIC=ROOT/'static'
HTML=(STATIC/'index.html').read_text(encoding='utf8').replace('<link rel="stylesheet" href="/style.css">','').replace('<script src="/app.js" defer></script>','')


def mocked_api(source,path,body):
    u=urlparse(path)
    if u.path=='/api/health':return {'ok':True,'ai_mode':'离线路由，未接入 LLM'}
    if u.path=='/api/diagnosis':return build_diagnosis(parse_qs(u.query).get('mode',['normal'])[0])
    if u.path=='/api/ask':
        obj=json.loads(body or '{}')
        return route_query(obj['question'],obj.get('mode','normal'))
    if u.path=='/api/pe':return scenario_pe(json.loads(body or '{}').get('price'))
    raise ValueError('Unknown API '+path)


def render(page):
    page.expose_binding('__apiMock',mocked_api)
    page.set_content(HTML,wait_until='domcontentloaded')
    page.add_style_tag(content=(STATIC/'style.css').read_text(encoding='utf8'))
    page.evaluate("""window.fetch = async (url,opts={}) => {let j=await window.__apiMock(url,opts.body || '');return new Response(JSON.stringify(j),{status:200,headers:{'Content-Type':'application/json'}})}; true""")
    errs=[]
    page.on('pageerror',lambda e:errs.append(str(e)))
    page.add_script_tag(content=(STATIC/'app.js').read_text(encoding='utf8'))
    page.wait_for_selector('.kpi',timeout=8000)
    return errs


with sync_playwright() as playwright:
    browser=playwright.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
    page=browser.new_page(viewport={'width':1440,'height':900})
    errors=render(page)
    assert page.locator('.kpi').count()==4
    assert page.locator('.evidence-card').count()==14
    page.screenshot(path=str(ROOT/'docs'/'UI_PREVIEW.png'),full_page=True)
    page.locator('.kpi').first.click()
    assert page.locator('#modal').is_visible()
    assert '#page=5' in page.locator('#modal a.source-link').first.get_attribute('href')
    page.locator('#modalClose').click()
    # An actual source-based text excerpt must say it's a paraphrase, not a verbatim quote
    page.locator('.evidence-card[data-eid="E12"]').click()
    assert '非逐字引用' in page.locator('#modalBody').inner_text()
    page.locator('#modalClose').click()
    page.locator('#modeSelect').select_option('offline')
    page.wait_for_function("document.querySelectorAll('.kpi-muted').length>=2")
    assert page.locator('.evidence-card[data-eid="E12"]').inner_text().find('数据异常')!=-1
    page.locator('#modeSelect').select_option('normal')
    page.wait_for_function("document.querySelectorAll('.kpi-muted').length===0")
    page.locator('#prompts button').first.click()
    page.wait_for_selector('#askAnswer .answer-group')
    assert '已核验事实' in page.locator('#askAnswer').inner_text()
    assert '谨慎推断' in page.locator('#askAnswer').inner_text()
    page.locator('#pePrice').fill('1500')
    page.locator('#peBtn').click()
    page.wait_for_function("document.querySelector('#peResult').textContent.includes('22.84')")
    assert not errors,errors

    mobile=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1)
    mobile_errors=render(mobile)
    assert mobile.locator('.evidence-card').count()==14
    assert mobile.locator('.sidebar').evaluate('(e)=>getComputedStyle(e).display')=='none'
    assert mobile.evaluate('document.documentElement.scrollWidth <= window.innerWidth+2'), 'unexpected horizontal overflow'
    mobile.screenshot(path=str(ROOT/'docs'/'UI_MOBILE_PREVIEW.png'),full_page=True)
    assert not mobile_errors,mobile_errors
    print('PASS: Chromium desktop/mobile, 4 KPI, 14 cards, anchored evidence, paraphrase flag, outage guard, structured Q&A, PE, no JS errors')
    browser.close()
