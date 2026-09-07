"""Browser checks against the real static app. pip install playwright; use installed Edge."""
import functools
import http.server
import json
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main():
    # Serve from repo root to exercise a non-root deployment path, like project Pages.
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/docs/'
    output = ROOT / 'test-results'
    output.mkdir(exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page(viewport={'width':1440,'height':1080},device_scale_factor=1)
            errors = []
            page.on('pageerror',lambda error: errors.append(str(error)))
            page.goto(url)
            page.wait_for_function("document.querySelector('#total-stat').textContent === '701'")
            assert page.locator('.word-card').count() == 18
            page.screenshot(path=str(output / 'desktop.png'),full_page=True)
            page.locator('#search').fill('concatenate')
            assert page.locator('.word-card').count() == 1
            page.get_by_role('button',name='concatenate',exact=True).click()
            assert 'Oscar:' in page.locator('#entry-detail').inner_text()
            assert page.locator('[data-edit]').count() == 0
            page.keyboard.press('Escape')
            page.locator('#search').fill('知识蒸馏')
            assert 'knowledge distillation' in page.locator('#cards').inner_text()
            page.locator('#reset').click()
            page.locator('[name=filter-domain][value="医学影像"]').check()
            assert page.locator('.word-card').count() == 4
            page.locator('#has-example').check()
            assert page.locator('.word-card').count() == 1
            page.locator('#reset').click()
            page.locator('[name=filter-pos][value=verb]').check()
            assert all(x == '动词' for x in page.locator('.word-card .pos-badge').all_text_contents())
            page.locator('#reset').click()
            page.get_by_role('button',name='下一页 →').click()
            assert '2 /' in page.locator('#pagination').inner_text()
            page.locator('#list-view').click()
            assert 'list-mode' in page.locator('#cards').get_attribute('class')
            page.locator('#search').fill('this-term-is-not-in-the-library')
            assert page.locator('.empty').is_visible()
            page.locator('#reset').click()
            page.locator('#auth-button').click()
            assert page.locator('#toast').is_visible()
            assert not page.locator('#auth-dialog').is_visible()
            # Exercise data handling, including stored markup and unsafe links.
            result = page.evaluate('''async () => {
              const m = await import('./lib.js');
              const entry = {term:'<img src=x onerror=alert(1)>',meaning:'测试',example:'',source:'',domains:['医学影像'],tags:['方法'],owner_id:'alice',pos:'noun'};
              const filters = {query:'测试',pos:new Set(['noun']),domains:new Set(['医学影像']),example:false,mine:true};
              return {
                escaped: !m.escapeHtml(entry.term).includes('<img'),
                unsafe: m.safeUrl('javascript:alert(1)') === '',
                owner: m.canEdit(entry,{id:'alice'},false),
                other: !m.canEdit(entry,{id:'bob'},false),
                admin: m.canEdit(entry,{id:'admin'},true),
                guest: !m.canEdit(entry,null,true),
                filter: m.filterEntries([entry],filters,{id:'alice'}).length === 1,
                tags: JSON.stringify(m.tagsFrom('医学, 医学，影像')) === JSON.stringify(['医学','影像'])
              };
            }''')
            assert all(result.values()),result
            page.locator('#grid-view').click()
            page.set_viewport_size({'width':390,'height':844})
            page.screenshot(path=str(output / 'mobile.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.get_by_role('button',name='✳ 随机认识一个词').click()
            assert page.locator('#entry-dialog').is_visible()
            assert page.evaluate('document.querySelector("#entry-dialog").getBoundingClientRect().width <= innerWidth')
            assert not errors,errors
            browser.close()
            print(json.dumps({'browser':'Edge','static_checks':'passed','data_checks':result,'console_errors':errors},ensure_ascii=False))
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
