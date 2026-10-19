"""Recent paper sources: reuse, bounded history, persistence, isolation, and storage failure."""
import functools
import http.server
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_smoke import QuietHandler

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ['source', 'source_venue', 'source_date', 'source_url']


def main():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 1080})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.add_init_script("window.mockInitialUser={id:'alice',user_metadata:{user_name:'Alice'}}")
            page.route('**/config.js*', lambda route: route.fulfill(content_type='text/javascript', body='window.VOCAB_CONFIG={supabaseUrl:"https://example.supabase.co",supabasePublishableKey:"test"};'))
            page.route('https://cdn.jsdelivr.net/**', lambda route: route.fulfill(content_type='text/javascript', body=(ROOT / 'tests/mock_supabase.js').read_text(encoding='utf-8')))
            page.goto(f'http://127.0.0.1:{server.server_port}/docs/')
            page.wait_for_function("document.querySelectorAll('.word-card').length === 2")

            def open_editor():
                page.locator('#add-entry').click()
                page.locator('#editor-dialog').wait_for()

            def values():
                return [page.locator(f'[name={field}]').input_value() for field in FIELDS]

            def save(term, source):
                page.locator('[name=term]').fill(term)
                page.locator('[name=meaning]').fill('meaning')
                for field, value in zip(FIELDS, source):
                    page.locator(f'[name={field}]').fill(value)
                page.locator('#save-entry').click()
                page.locator('#editor-dialog').wait_for(state='hidden')

            papers = [[f'Paper {i}', f'Venue {i}', f'202{i}-06', f'https://doi.org/example-{i}'] for i in range(4)]
            open_editor()
            assert page.locator('#source-history').is_hidden()
            save('history first', papers[0])
            open_editor()
            assert values() == ['', '', '', ''], 'Opening must not silently fill a source'
            page.locator('[name=example]').fill('Keep this example')
            page.locator('[name=term]').fill('history second')
            page.locator('#recent-source').select_option('0')
            assert values() == papers[0]
            assert page.locator('[name=term]').input_value() == 'history second'
            assert page.locator('[name=example]').input_value() == 'Keep this example'
            save('history second', papers[0])
            open_editor()
            assert page.locator('#recent-source option').count() == 2, 'Identical sources must not be duplicated'
            for i in range(1, 4):
                save(f'history paper {i}', papers[i])
                open_editor()
            assert page.locator('#recent-source option').count() == 4
            assert 'Paper 0' not in page.locator('#recent-source').inner_text()
            page.locator('#recent-source').select_option('0')
            assert values() == papers[3]
            page.locator('#recent-source').select_option('2')
            assert values() == papers[1]
            save('history reused', papers[1])
            open_editor()
            page.locator('#recent-source').select_option('0')
            assert values() == papers[1], 'A saved reused source must become most recent'
            # Failed writes must leave history unchanged.
            page.evaluate('window.mockWriteError=true')
            page.locator('[name=term]').fill('history failed')
            page.locator('[name=meaning]').fill('meaning')
            page.locator('[name=source]').fill('Should not enter history')
            page.locator('#save-entry').click()
            page.wait_for_function("document.querySelector('#editor-error').textContent.length > 0")
            page.keyboard.press('Escape')
            page.reload()
            page.wait_for_function("document.querySelectorAll('.word-card').length === 2")
            open_editor()
            page.locator('#recent-source').select_option('0')
            assert values() == papers[1], 'History must survive a reload and exclude failed saves'
            assert 'Should not enter history' not in page.locator('#recent-source').inner_text()
            # A selection also clears fields that are blank in the selected source.
            title = ('<img src=x onerror=window.injected=true> ' + 'A long paper title ' * 12).strip()
            save('partial source', [title, '', '', ''])
            open_editor()
            for field in FIELDS:
                page.locator(f'[name={field}]').fill('old value')
            page.locator('#recent-source').select_option('0')
            assert values() == [title, '', '', '']
            assert page.locator('#source-history img').count() == 0
            assert page.evaluate('window.injected !== true')
            (ROOT / 'test-results').mkdir(exist_ok=True)
            for width in (1440, 390):
                page.set_viewport_size({'width': width, 'height': 1080})
                assert page.locator('#editor-dialog').evaluate('(e) => e.scrollWidth <= e.clientWidth')
                page.locator('#source-history').scroll_into_view_if_needed()
                page.screenshot(path=str(ROOT / 'test-results' / f'source-history-{width}.png'))
            page.keyboard.press('Escape')
            page.evaluate("mockSignIn('bob')")
            page.wait_for_function("document.querySelector('#auth-button').textContent.includes('退出')")
            open_editor()
            assert page.locator('#source-history').is_hidden(), 'Accounts must have separate histories'
            # Block storage writes: saving still succeeds and history works for this visit.
            page.evaluate("() => { Storage.prototype.setItem = () => { throw new DOMException('blocked', 'SecurityError'); }; }")
            save('storage blocked', papers[2])
            open_editor()
            page.locator('#recent-source').select_option('0')
            assert values() == papers[2]
            assert not errors, errors
            browser.close()
            print('PASS: recent paper sources, four-field reuse, deduplication, recency, limit, persistence, failed saves, account isolation, mobile layout, storage fallback.')
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
