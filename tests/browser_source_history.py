"""Recent paper sources: cross-device sync, local import, privacy, and failure handling."""
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
            cloud = {}

            def merge_sources(user_id, incoming, promote):
                existing = cloud.get(user_id, [])
                result = []
                for item in (incoming + existing if promote else existing + incoming):
                    source = {field: item.get(field, '').strip() for field in FIELDS}
                    if any(source.values()) and source not in result:
                        result.append(source)
                cloud[user_id] = result[:3]
                return cloud[user_id]

            page = browser.new_page(viewport={'width': 1440, 'height': 1080})
            page.expose_function('mockSourceCloud', merge_sources)
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
                page.wait_for_function("document.querySelector('#recent-source').getAttribute('aria-busy') === 'false'")

            def select_source(index, target=None):
                target = target or page
                target.locator('#source-title').click()
                target.locator('#recent-source [role=option]').nth(index).click()
                assert target.locator('#source-history').is_hidden()

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
            select_source(0)
            assert values() == papers[0]
            assert page.locator('[name=term]').input_value() == 'history second'
            assert page.locator('[name=example]').input_value() == 'Keep this example'
            save('history second', papers[0])
            open_editor()
            assert page.locator('#recent-source [role=option]').count() == 1, 'Identical sources must not be duplicated'
            assert page.locator('#recent-source [role=option]').all_text_contents() == ['Paper 0'], 'Suggestions must only display paper titles'
            page.locator('#source-title').click()
            assert page.locator('.source-history-heading').inner_text() == '最近读过的论文'
            assert page.locator('#source-history-note').is_hidden()
            page.locator('#source-title').press('Escape')
            for i in range(1, 4):
                save(f'history paper {i}', papers[i])
                open_editor()
            assert page.locator('#recent-source [role=option]').count() == 3
            assert 'Paper 0' not in page.locator('#recent-source').inner_text()
            select_source(0)
            assert values() == papers[3]
            select_source(2)
            assert values() == papers[1]
            save('history reused', papers[1])
            open_editor()
            select_source(0)
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
            select_source(0)
            assert values() == papers[1], 'History must survive a reload and exclude failed saves'
            assert 'Should not enter history' not in page.locator('#recent-source').inner_text()
            assert page.locator('#source-history-note').is_hidden()
            # A second browser context has no local history and receives the same account data.
            device = browser.new_context(viewport={'width': 390, 'height': 1080}, has_touch=True, is_mobile=True)
            device.expose_function('mockSourceCloud', merge_sources)
            device.add_init_script("window.mockInitialUser={id:'alice',user_metadata:{user_name:'Alice'}}")
            device.route('**/config.js*', lambda route: route.fulfill(content_type='text/javascript', body='window.VOCAB_CONFIG={supabaseUrl:"https://example.supabase.co",supabasePublishableKey:"test"};'))
            device.route('https://cdn.jsdelivr.net/**', lambda route: route.fulfill(content_type='text/javascript', body=(ROOT / 'tests/mock_supabase.js').read_text(encoding='utf-8')))
            second = device.new_page()
            second.goto(page.url)
            second.wait_for_function("document.querySelectorAll('.word-card').length === 2")
            assert second.evaluate("localStorage.getItem('paperlex:recent-sources:alice')") is None
            second.locator('#add-entry').click()
            second.wait_for_function("document.querySelector('#recent-source').getAttribute('aria-busy') === 'false'")
            second.locator('#source-title').tap()
            second.locator('#recent-source [role=option]').nth(0).tap()
            assert second.locator('#source-history').is_hidden()
            assert [second.locator(f'[name={field}]').input_value() for field in FIELDS] == papers[1]
            # A save on the second device updates history seen on the first device.
            second.locator('[name=term]').fill('second device word')
            second.locator('[name=meaning]').fill('meaning')
            second.locator('[name=source]').fill('From phone')
            second.locator('#save-entry').click()
            second.locator('#editor-dialog').wait_for(state='hidden')
            device.close()
            page.keyboard.press('Escape')
            open_editor()
            select_source(0)
            assert values()[0] == 'From phone', 'Reopening must fetch changes made on another device'
            # A selection also clears fields that are blank in the selected source.
            title = ('<img src=x onerror=window.injected=true> ' + 'A long paper title ' * 12).strip()
            save('partial source', [title, '', '', ''])
            open_editor()
            for field in FIELDS:
                page.locator(f'[name={field}]').fill('old value')
            select_source(0)
            assert values() == [title, '', '', '']
            assert page.locator('#source-history img').count() == 0
            assert page.evaluate('window.injected !== true')
            # Suggestions appear below the title, support keys, and never submit the form.
            page.locator('#source-title').click()
            assert page.locator('#source-title').get_attribute('aria-expanded') == 'true'
            assert page.locator('#source-history').bounding_box()['y'] >= page.locator('#source-title').bounding_box()['y'] + page.locator('#source-title').bounding_box()['height']
            writes = page.evaluate("mockCalls.filter(c => c[0] === 'insert').length")
            page.locator('#source-title').press('ArrowDown')
            assert page.locator('#source-title').get_attribute('aria-activedescendant') == 'recent-source-0'
            page.locator('#source-title').press('Enter')
            assert values() == [title, '', '', '']
            assert page.locator('#source-history').is_hidden()
            assert page.evaluate("mockCalls.filter(c => c[0] === 'insert').length") == writes
            page.locator('#source-title').click()
            page.locator('#source-title').press('ArrowUp')
            page.locator('#source-title').press('Enter')
            assert values()[0] == cloud['alice'][-1]['source']
            page.locator('#source-title').click()
            page.locator('#source-title').press('Escape')
            assert page.locator('#source-history').is_hidden()
            assert page.locator('#editor-dialog').is_visible()
            page.locator('#source-title').click()
            page.locator('[name=meaning]').click()
            assert page.locator('#source-history').is_hidden()
            page.locator('#source-title').fill('A custom draft')
            page.locator('#source-title').press('Tab')
            assert page.locator('#source-history').is_hidden()
            assert values()[0] == 'A custom draft'
            select_source(0)
            (ROOT / 'test-results').mkdir(exist_ok=True)
            for width in (1440, 390):
                page.set_viewport_size({'width': width, 'height': 1080})
                assert page.locator('#editor-dialog').evaluate('(e) => e.scrollWidth <= e.clientWidth')
                page.locator('#source-title').click()
                page.locator('#source-history').scroll_into_view_if_needed()
                page.screenshot(path=str(ROOT / 'test-results' / f'source-history-{width}.png'))
            page.keyboard.press('Escape')
            page.evaluate("mockSignIn('bob')")
            page.wait_for_function("document.querySelector('#auth-button').textContent.includes('退出')")
            open_editor()
            assert page.locator('#source-history').is_hidden(), 'Accounts must have separate histories'
            # Import the history left by the earlier browser-only version.
            legacy = dict(zip(FIELDS, papers[0]))
            page.evaluate("source => localStorage.setItem('paperlex:recent-sources:bob', JSON.stringify([source]))", legacy)
            page.keyboard.press('Escape')
            open_editor()
            select_source(0)
            assert values() == papers[0]
            assert cloud['bob'] == [legacy]
            # Block storage writes: saving still succeeds and history works for this visit.
            page.evaluate("() => { Storage.prototype.setItem = () => { throw new DOMException('blocked', 'SecurityError'); }; }")
            save('storage blocked', papers[2])
            open_editor()
            select_source(0)
            assert values() == papers[2]
            assert page.locator('#source-history-note').is_hidden()
            # Missing migration/network errors keep fallback history and never block entry saves.
            page.evaluate('window.mockSourceError=true')
            page.keyboard.press('Escape')
            open_editor()
            assert '暂时无法同步' in page.locator('#source-history-note').inner_text()
            save('source service unavailable', papers[3])
            open_editor()
            select_source(0)
            assert values() == papers[3]
            page.evaluate('window.mockSourceError=false')
            page.keyboard.press('Escape')
            open_editor()
            assert page.locator('#source-history-note').is_hidden()
            # Token refresh must not discard a legitimate in-flight sync response.
            page.keyboard.press('Escape')
            page.evaluate('window.mockSourceDelay=400')
            page.locator('#add-entry').click()
            page.evaluate('mockRefresh()')
            page.wait_for_function("document.querySelector('#recent-source').getAttribute('aria-busy') === 'false'")
            assert page.locator('#source-history-note').is_hidden()
            # A late response from the old account must not replace the new account's history.
            page.keyboard.press('Escape')
            page.locator('#add-entry').click()
            page.evaluate("mockSignIn('alice')")
            page.locator('#editor-dialog').wait_for(state='hidden')
            page.evaluate('window.mockSourceDelay=0')
            open_editor()
            select_source(0)
            assert values()[0] == title
            page.wait_for_timeout(500)
            select_source(0)
            assert values()[0] == title, 'A response for Bob must not appear under Alice'
            # Untitled sources are not displayed, but selection still uses the matching source record.
            cloud['alice'] = [dict(zip(FIELDS, ['', 'Venue only', '2025', ''])), *cloud['alice']][:3]
            page.keyboard.press('Escape')
            open_editor()
            page.locator('#source-title').click()
            assert page.locator('#recent-source [role=option]').count() == 2
            assert page.locator('#recent-source small').count() == 0
            page.locator('#source-title').press('ArrowDown')
            page.locator('#source-title').press('Enter')
            assert values() == [cloud['alice'][1][field] for field in FIELDS]
            assert not errors, errors
            browser.close()
            print('PASS: cross-device paper sources, local import, deduplication, recent limit, failed saves, account isolation, mobile layout, storage and network fallback.')
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
