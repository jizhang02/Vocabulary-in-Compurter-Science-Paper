"""Coverage and provenance checks for the bundled vocabulary snapshot."""
import collections
import datetime
import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = json.loads((ROOT / 'docs/data/vocabulary.json').read_text(encoding='utf-8'))
        cls.annotations = json.loads((ROOT / 'data/example_annotations.json').read_text(encoding='utf-8'))['entries']
        cls.evidence = json.loads((ROOT / 'data/example_evidence.json').read_text(encoding='utf-8'))

    def test_complete_coverage_and_identity(self):
        ids = {e['id'] for e in self.entries}
        self.assertEqual(ids, set(self.annotations))
        self.assertEqual(ids, set(self.evidence))
        for e in self.entries:
            with self.subTest(term=e['term']):
                a = self.annotations[e['id']]
                self.assertEqual((e['term'], e['meaning']), (a['term'], a['meaning']))
                self.assertTrue(e['example'].strip())
                self.assertEqual(e['example'], a['example'])
                ev = self.evidence[e['id']]
                self.assertEqual(hashlib.sha256(e['example'].encode()).hexdigest(), ev['example_sha256'])
                self.assertIn(ev['matched_form'].casefold(), e['example'].casefold())

    def test_provenance_and_real_date_precision(self):
        for e in self.entries:
            with self.subTest(term=e['term']):
                for key in ['source', 'source_venue', 'source_date', 'source_location']:
                    self.assertTrue(e[key].strip(), key)
                date = e['source_date']
                self.assertRegex(date, r'^\d{4}(-\d{2}(-\d{2})?)?$')
                parts = [int(p) for p in date.split('-')]
                supplied = datetime.date(*(parts + [1] * (3-len(parts))))
                self.assertLessEqual(supplied, datetime.date(2026, 9, 9))
                ev = self.evidence[e['id']]
                if ev['kind'] == 'authored':
                    self.assertEqual(e['source_venue'], '自拟例句')
                    self.assertIn('非论文原文', e['source_location'])
                    self.assertEqual(e['source_url'], '')
                else:
                    self.assertRegex(e['source_url'], r'^https://')
                    self.assertRegex(ev['evidence_url'], r'^https://')
                    self.assertNotIn('待复核', e['source_location'])

    def test_short_quotations_and_rejected_false_friends(self):
        by_source = collections.defaultdict(set)
        for e in self.entries:
            if not e['source_url']:
                continue
            url = e['source_url'].lower().rstrip('/')
            if 'nature.com/articles/' in url:
                url = 'https://doi.org/10.1038/' + url.split('/articles/')[1]
            by_source[url].add(e['example'])
        for url, snippets in by_source.items():
            self.assertLessEqual(sum(len(s.replace('…', '').split()) for s in snippets), 25, url)
        by_term = {e['term']: e for e in self.entries}
        self.assertNotIn('Cucurbita', by_term['squash']['example'])
        self.assertNotIn('TWEAK', by_term['tweak']['example'])
        self.assertNotIn('BAIL', by_term['bail']['example'])
        self.assertNotIn('Maxwell', by_term['daemon']['example'])
        self.assertNotIn('crop biomass', by_term['crop']['example'])


if __name__ == '__main__':
    unittest.main()
