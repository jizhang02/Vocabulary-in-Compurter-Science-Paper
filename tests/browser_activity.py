"""Activity reporting contracts with a mock SDK and a controlled browser clock."""
import functools
import http.server
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_smoke import QuietHandler

ROOT = Path(__file__).resolve().parents[1]


def main():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page()
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.clock.install()
            page.route('**/config.js*', lambda route: route.fulfill(content_type='text/javascript', body='window.VOCAB_CONFIG={supabaseUrl:"https://example.supabase.co",supabasePublishableKey:"test"};'))
            page.route('https://cdn.jsdelivr.net/**', lambda route: route.fulfill(content_type='text/javascript', body=(ROOT/'tests/mock_supabase.js').read_text(encoding='utf-8')))
            page.goto(f'http://127.0.0.1:{server.server_port}/docs/')
            page.wait_for_function("document.querySelector('#result-count').textContent.includes('共 2 个')")
            calls = lambda: page.evaluate("mockCalls.filter(c=>c[0]==='record_activity').length")
            assert calls() == 0
            page.evaluate("mockSignIn('alice')")
            page.wait_for_function("mockCalls.some(c=>c[0]==='record_activity' && c[1]==='alice')")
            assert calls() == 1
            page.evaluate("window.dispatchEvent(new Event('focus'))")
            assert calls() == 1, 'Rapid focus events must be throttled'
            page.clock.fast_forward(61000)
            assert calls() == 2, 'Visible pages should report periodically'
            page.evaluate("Object.defineProperty(document,'visibilityState',{configurable:true,value:'hidden'}); document.dispatchEvent(new Event('visibilitychange'))")
            page.clock.fast_forward(61000)
            assert calls() == 2, 'Hidden pages must not report activity'
            page.evaluate("Object.defineProperty(document,'visibilityState',{configurable:true,value:'visible'}); document.dispatchEvent(new Event('visibilitychange'))")
            page.wait_for_function("mockCalls.filter(c=>c[0]==='record_activity').length === 3")
            page.evaluate('window.mockActivityError=true')
            page.clock.fast_forward(61000)
            assert calls() == 4
            page.locator('#my-contributions').click()
            assert page.locator('.word-card').count() == 1, 'Failed activity reports must not block the app'
            page.evaluate('window.mockActivityError=false')
            page.clock.fast_forward(61000)
            assert calls() == 5, 'A failed report should retry later'
            page.locator('#auth-button').click()
            page.wait_for_function("document.querySelector('#auth-button').textContent === '登录 / 注册'")
            page.clock.fast_forward(61000)
            assert calls() == 5, 'Logout must stop reports'
            page.evaluate("mockSignIn('bob')")
            page.wait_for_function("mockCalls.some(c=>c[0]==='record_activity' && c[1]==='bob')")
            assert calls() == 6
            assert not errors, errors
            browser.close()
            print('PASS: visible heartbeat, focus throttle, background suppression, error recovery, logout and account switch.')
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
