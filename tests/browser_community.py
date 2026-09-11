"""UI contracts with a mocked SDK; no real emails or cloud mutations."""
import functools
import http.server
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_smoke import QuietHandler

ROOT = Path(__file__).resolve().parents[1]


def main():
    server = http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(ROOT)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge',headless=True)
            page = browser.new_page()
            errors = []
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.route('**/config.js*',lambda route:route.fulfill(content_type='text/javascript',body='window.VOCAB_CONFIG={supabaseUrl:"https://example.supabase.co",supabasePublishableKey:"test"};'))
            page.route('https://cdn.jsdelivr.net/**',lambda route:route.fulfill(content_type='text/javascript',body=(ROOT/'tests/mock_supabase.js').read_text(encoding='utf-8')))
            page.goto(f'http://127.0.0.1:{server.server_port}/docs/')
            page.wait_for_function("document.querySelector('#total-stat').textContent === '2'")
            # Cloud is authoritative: bundled entries must not reappear.
            assert page.locator('.word-card').count() == 2
            page.locator('#auth-button').click()
            page.locator('#github-login').click()
            assert page.evaluate("mockCalls.some(c=>c[0]==='oauth' && c[1].provider==='github' && c[1].options.redirectTo.endsWith('/docs/'))")
            assert page.locator('#auth-dialog input').count() == 0
            page.keyboard.press("Escape")  # OAuth normally navigates away from the dialog.
            page.evaluate("mockSignIn('alice')")
            page.wait_for_function("document.querySelector('#auth-button').textContent.includes('已登录')")
            page.locator('#my-contributions').click()
            assert page.locator('.word-card').count() == 1
            page.locator('#reset').click()
            page.get_by_role('button',name='展开 other term',exact=True).click()
            assert page.locator('[data-edit]').count() == 0
            assert page.locator('#entry-detail img').count() == 0
            assert page.locator('#entry-detail a').count() == 0
            page.keyboard.press('Escape')
            page.get_by_role('button',name='展开 own term',exact=True).click()
            page.get_by_role('button',name='修改词汇',exact=True).click()
            assert page.locator('[name=domains][value=医学]').is_checked()
            assert page.locator('[name=tags], [name=source_location]').count() == 0
            page.locator('[name=meaning]').fill('修改后的释义')
            page.evaluate('mockRefresh()')
            page.wait_for_timeout(100)
            assert page.locator('#editor-dialog').is_visible(), 'Token refresh must preserve an open draft'
            page.locator('#save-entry').click()
            page.wait_for_selector('#editor-dialog',state='hidden')
            assert '修改后的释义' in page.locator('#cards').inner_text()
            page.locator('#add-entry').click()
            page.locator('[name=term]').fill('  OWN   TERM  ')
            page.locator('[name=meaning]').fill('重复测试')
            page.locator('#save-entry').click()
            page.wait_for_function("document.querySelector('#editor-error').textContent.includes('已存在')")
            assert page.evaluate("mockCalls.filter(c => c[0] === 'insert').length") == 0
            page.locator('[name=term]').fill('new term')
            page.locator('[name=meaning]').fill('新词')
            page.locator('[name=domains][value=机器学习]').check()
            page.locator('[name=domains][value=医学]').check()
            page.locator('#save-entry').click()
            page.wait_for_function("document.querySelector('#total-stat').textContent === '3'")
            assert page.evaluate("mockCalls.some(c => c[0] === 'insert' && c[1].domains.length === 2 && c[1].domains.includes('医学'))")
            page.get_by_role('button',name='展开 own term',exact=True).click()
            page.get_by_role('button',name='修改词汇',exact=True).click()
            page.evaluate('window.mockConflict=true')
            page.locator('#save-entry').click()
            page.wait_for_function("document.querySelector('#editor-error').textContent.includes('其他人修改')")
            assert page.locator('#editor-dialog').is_visible()
            page.keyboard.press('Escape')
            page.evaluate('window.mockConflict=false; mockSignIn("admin")')
            page.wait_for_function("document.querySelector('#auth-button').textContent.includes('管理员')")
            page.get_by_role('button',name='展开 other term',exact=True).click()
            assert page.locator('[data-edit]').count() == 1
            page.on('dialog',lambda dialog:dialog.accept())
            page.get_by_role('button',name='删除词汇',exact=True).click()
            page.wait_for_function("document.querySelector('#total-stat').textContent === '2'")
            assert 'other term' not in page.locator('#cards').inner_text()
            page.locator('#auth-button').click()
            page.wait_for_function("document.querySelector('#auth-button').textContent === '登录 / 注册'")
            assert page.locator('#mine').count() == 0
            assert page.locator('.word-card').count() == 2
            assert not errors,errors
            browser.close()
            print('PASS: GitHub-only login UI, keyset pagination, owner UI, CRUD, admin UI, conflict handling, session refresh, XSS escaping, logout (mock SDK).')
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
