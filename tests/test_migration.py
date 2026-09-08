import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("migration",ROOT / "scripts/migrate_glossary.py")
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class MigrationTests(unittest.TestCase):
    def test_domain_coverage_and_semantic_boundaries(self):
        entries = json.loads((ROOT / 'docs/data/vocabulary.json').read_text(encoding='utf-8'))
        allowed = set(migration.ANNOTATIONS['allowed_domains'])
        self.assertEqual(len(migration.ANNOTATIONS['entries']), len(entries))
        for entry in entries:
            self.assertTrue(entry['domains'], entry['term'])
            self.assertTrue(set(entry['domains']) <= allowed, entry['term'])
            self.assertEqual(len(entry['domains']), len(set(entry['domains'])))
        by_term = {e['term']: e for e in entries}
        # A medical/ML source does not make an ordinary expression a technical term.
        self.assertEqual(by_term['substantial']['domains'], ['通用'])
        self.assertEqual(by_term['with respect to']['domains'], ['通用'])
        self.assertEqual(by_term['in a nutshell']['domains'], ['通用'])
        self.assertIn('自然语言处理', by_term['tokenization']['domains'])
        self.assertIn('医学', by_term['hypointense']['domains'])
        self.assertIn('数学', by_term['posteriori probability']['domains'])
        self.assertIn('机器学习', by_term['knowledge distillation']['domains'])
        self.assertEqual(by_term['valve']['domains'], ['通用'])
        self.assertEqual(by_term['prime']['domains'], ['通用'])
        original = by_term['substantial']
        self.assertEqual(migration.domains_for(original['id'], 'new word', original['meaning'], original['pos']), [])

    def test_rows_preserved_and_placeholders_removed(self):
        entries = migration.parse_markdown((ROOT / "docs/glossary_v2.md").read_text(encoding="utf-8"))
        self.assertGreater(len(entries), 600)
        self.assertEqual(len({e['id'] for e in entries}),len(entries))
        self.assertFalse(any(e['term'] == 'word' and e['meaning'] == '中文' for e in entries))
        self.assertFalse(any(e['example'] == 'sentence.' for e in entries))
        self.assertTrue(all('<details>' not in e['source'] for e in entries))
        concatenate = next(e for e in entries if e['term'] == 'concatenate')
        self.assertIn('concatenate the object',concatenate['example'])
        self.assertIn('Oscar:',concatenate['source'])
        self.assertEqual(concatenate['meaning'],'连接')
        saved = json.loads((ROOT / 'docs/data/vocabulary.json').read_text(encoding='utf-8'))
        self.assertEqual(entries,saved)

    def test_duplicate_words_and_distinct_senses_are_not_lost(self):
        sample = '''## Verb
| 1 | test | 检验 | <details><summary>Click</summary> *`We test it.`* Paper, 2025.</details> | 2 | test | 试验 | <details><summary>Click</summary> *`sentence.`* journal, 2020.</details> |
## Noun
| 1 | test | 测试 | <details><summary>Click</summary> *`A test.`* Source.</details> |
'''
        entries = migration.parse_markdown(sample)
        self.assertEqual(len(entries),3)
        self.assertEqual(entries[1]['example'],'')
        self.assertEqual(entries[1]['source'],'')
        self.assertEqual(entries[2]['pos'],'noun')
        self.assertEqual(len({e['id'] for e in entries}),3)


if __name__ == '__main__':
    unittest.main()
