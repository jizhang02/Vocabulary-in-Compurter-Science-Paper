"""Public export completeness, readable output and failure preservation."""
import importlib.util
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('backup', ROOT / 'scripts/backup_vocabulary.py')
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def entry(number, **changes):
    result = dict(id=f'00000000-0000-0000-0000-{number:012d}', term=f'term {number}',
                  meaning='中文释义', pos='noun', domains=['医学'], tags=[], revision=1)
    result.update(changes)
    return result


class BackupTests(unittest.TestCase):
    def test_pagination_below_requested_cap_and_public_fields(self):
        calls = []

        def reader(url, key, params):
            calls.append(params)
            if 'id' not in params:
                return [entry(1)], 2
            if params['id'] == 'gt.' + entry(1)['id']:
                return [entry(2)], 1
            return [], 0

        result = backup.fetch_entries('https://example.supabase.co', 'public', reader)
        self.assertEqual([e['id'] for e in result], [entry(1)['id'], entry(2)['id']])
        self.assertEqual(len(calls), 6)
        self.assertNotIn('owner_id', calls[0]['select'])

    def test_same_count_replacement_or_edit_during_export_fails(self):
        for newer in (entry(2), entry(1, revision=2)):
            pages = iter([([entry(1)], 1), ([], 0), ([newer], 1), ([], 0)])
            with self.subTest(newer=newer), self.assertRaisesRegex(ValueError, 'changed during export'):
                backup.fetch_entries('https://example.supabase.co', 'public', lambda *args: next(pages))

    def test_malformed_urls_are_preserved_as_literal_text(self):
        for url in ('http://[broken', 'https://', 'javascript:alert(1)'):
            text = backup.render_markdown([entry(1, source_url=url)])
            self.assertIn('来源链接（原始文本）', text)
            self.assertNotIn('[查看来源]', text)

    def test_changed_count_missing_rows_and_duplicate_pages_fail(self):
        for responses in (
            [([entry(1)], 2), ([], 0)],
            [([entry(1)], 2), ([entry(1)], 1)],
            [([], 2)],
            [([], 0)],
        ):
            pages = iter(responses)
            with self.subTest(responses=responses), self.assertRaises(ValueError):
                backup.fetch_entries('https://example.supabase.co', 'public', lambda *args: next(pages))

    def test_public_request_and_exact_count_required(self):
        class Response(io.BytesIO):
            headers = {'Content-Range': '0-0/1'}

        def opener(request, timeout):
            self.assertEqual(request.get_header('Apikey'), 'sb_publishable_test')
            self.assertIsNone(request.get_header('Authorization'))
            self.assertIn('count=exact', request.get_header('Prefer'))
            self.assertNotIn('owner_id', request.full_url)
            return Response(json.dumps([entry(1)]).encode())

        rows, count = backup.read_page('https://example.supabase.co', 'sb_publishable_test', {}, opener)
        self.assertEqual(count, 1)
        self.assertEqual(rows[0]['id'], entry(1)['id'])

    def test_missing_count_and_non_array_response_fail(self):
        class Response(io.BytesIO):
            pass

        for payload, headers in (([entry(1)], {}), ({'error': 'not entries'}, {'Content-Range': '0-0/1'})):
            def opener(*args, **kwargs):
                response = Response(json.dumps(payload).encode())
                response.headers = headers
                return response

            with self.subTest(payload=payload), self.assertRaises(ValueError):
                backup.read_page('https://example.supabase.co', 'public', {}, opener)

    def test_transient_errors_retry_but_auth_failures_stop(self):
        class Response(io.BytesIO):
            headers = {'Content-Range': '0-0/1'}

        attempts = []

        def opener(request, timeout):
            attempts.append(request)
            if len(attempts) == 1:
                raise urllib.error.HTTPError(request.full_url, 503, 'unavailable', {}, None)
            return Response(json.dumps([entry(1)]).encode())

        with patch.object(backup.time, 'sleep') as sleep:
            self.assertEqual(backup.read_page('https://example.supabase.co', 'public', {}, opener)[1], 1)
            self.assertEqual(len(attempts), 2)
            sleep.assert_called_once_with(1)
        error = urllib.error.HTTPError('https://example.supabase.co', 401, 'do not expose response', {}, None)
        with patch.object(backup.time, 'sleep') as sleep, \
             self.assertRaisesRegex(ValueError, 'HTTP 401'):
            backup.read_page('https://example.supabase.co', 'public', {}, lambda *args, **kwargs: (_ for _ in ()).throw(error))
        sleep.assert_not_called()

    def test_markdown_is_sorted_and_untrusted_content_is_literal(self):
        first = entry(1)
        first.update(term='Alpha <script>', meaning='释义 [click](javascript:alert(1))',
                     domains=['机器学习', '计算机科学', '医学'], example='line one\n<img src=x>',
                     source='论文', source_url='https://example.org/a(b)', author_name='贡献者')
        second = entry(2)
        second['term'] = 'Zulu'
        text = backup.render_markdown([second, first])
        self.assertLess(text.index('### Alpha'), text.index('### Zulu'))
        self.assertIn('计算机科学 / 医学', text)
        self.assertNotIn('机器学习', text)
        self.assertNotIn('<script>', text)
        self.assertNotIn('<img', text)
        self.assertNotIn('[click](javascript:', text)
        self.assertIn('https://example.org/a%28b%29', text)
        self.assertIn('> line one\n> &lt;img src=x&gt;', text)
        self.assertEqual(text, backup.render_markdown([first, second]))
        self.assertIn('**1 个词条有例句**', text)
        self.assertIn('**1 个词条待补例句**', text)
        multiline = backup.render_markdown([entry(1, example='first\n\nlast')])
        self.assertIn('> first\n>\n> last', multiline)
        self.assertTrue(all(line == line.rstrip() for line in multiline.splitlines()))

    def test_failed_export_preserves_previous_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'vocabulary.md'
            path.write_text('previous complete backup', encoding='utf-8')
            with patch.object(backup, 'configuration', return_value=('url', 'key')), \
                 patch.object(backup, 'fetch_entries', side_effect=ValueError('Empty response')), \
                 patch('sys.argv', ['backup', '--output', str(path)]), \
                 patch('sys.stderr', new_callable=io.StringIO), \
                 self.assertRaises(SystemExit):
                backup.main()
            self.assertEqual(path.read_text(encoding='utf-8'), 'previous complete backup')


if __name__ == '__main__':
    unittest.main()
