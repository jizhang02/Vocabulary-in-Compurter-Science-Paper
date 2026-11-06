"""Export public Supabase entries to a stable, readable Markdown snapshot (stdlib only)."""
import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
FIELDS = (
    'id', 'term', 'meaning', 'pos', 'domains', 'tags', 'example', 'source',
    'source_venue', 'source_date', 'source_location', 'source_url', 'author_name',
    'provenance', 'created_at', 'updated_at', 'revision',
)
POSITIONS = {'verb': '动词', 'adjective-adverb': '形容词 / 副词', 'noun': '名词', 'phrase': '短语'}
LEGACY_DOMAINS = {'机器学习', '计算机视觉', '自然语言处理'}


def configuration():
    """Reuse the website's public read access; no privileged database key is needed."""
    text = (ROOT / 'docs/config.js').read_text(encoding='utf-8')

    def value(env, field):
        match = re.search(r'\b' + field + r'\s*:\s*["\']([^"\']+)["\']', text)
        return os.environ.get(env) or (match.group(1) if match else '')

    url = value('SUPABASE_URL', 'supabaseUrl').rstrip('/')
    key = value('SUPABASE_PUBLISHABLE_KEY', 'supabasePublishableKey')
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
        raise ValueError('Configure a valid HTTPS SUPABASE_URL and public read key.')
    if not key:
        raise ValueError('Configure SUPABASE_PUBLISHABLE_KEY or docs/config.js.')
    return url, key


def read_page(url, key, params, opener=urllib.request.urlopen):
    headers = {'apikey': key, 'Accept': 'application/json', 'Prefer': 'count=exact'}
    # Legacy anon JWT keys also need Bearer authorization; sb_publishable keys do not.
    if key.startswith('eyJ'):
        headers['Authorization'] = 'Bearer ' + key
    request = urllib.request.Request(url + '/rest/v1/entries?' + urllib.parse.urlencode(params), headers=headers)
    for attempt in range(3):
        try:
            with opener(request, timeout=60) as response:
                payload = json.load(response)
                count = response.headers.get('Content-Range', '').rsplit('/', 1)[-1]
            if not isinstance(payload, list) or not count.isdigit():
                raise ValueError('Invalid entries response or missing exact row count; backup unchanged.')
            return payload, int(count)
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise ValueError(f'Supabase returned HTTP {error.code}; backup unchanged.') from None
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise ValueError('Supabase request failed; backup unchanged.') from None
        time.sleep(2 ** attempt)


def fetch_rows(url, key, fields, reader):
    entries, last, expected = [], None, None
    while True:
        params = {'select': ','.join(fields), 'order': 'id.asc', 'limit': '500'}
        if last:
            params['id'] = 'gt.' + last
        batch, remaining = reader(url, key, params)
        if expected is None:
            expected = remaining
        if remaining != expected - len(entries):
            raise ValueError('Entry count changed during export; retry the backup.')
        if not batch:
            break
        for entry in batch:
            if not isinstance(entry, dict):
                raise ValueError('Invalid entry received; backup unchanged.')
            entry_id = entry.get('id', '')
            if not isinstance(entry_id, str) or str(UUID(entry_id)) != entry_id:
                raise ValueError('Invalid entry ID; backup unchanged.')
            if last is not None and entry_id <= last:
                raise ValueError('Entries are duplicated or out of order; backup unchanged.')
            if type(entry.get('revision')) is not int or entry['revision'] < 1:
                raise ValueError('Invalid entry revision; backup unchanged.')
            last = entry_id
            entries.append(entry)
        # Continue even if the server caps pages below the requested size.
    if len(entries) != expected:
        raise ValueError('Incomplete export; backup unchanged.')
    if not entries:
        raise ValueError('Empty vocabulary received; refusing to replace the backup.')
    return entries


def fetch_entries(url, key, reader=read_page):
    entries = fetch_rows(url, key, FIELDS, reader)
    for entry in entries:
        if any(not isinstance(entry.get(field, ''), str) for field in FIELDS
               if field not in ('domains', 'tags', 'revision')):
            raise ValueError('Invalid entry text; backup unchanged.')
        if not entry.get('term', '').strip() or not entry.get('meaning', '').strip() or entry.get('pos') not in POSITIONS:
            raise ValueError('Incomplete entry received; backup unchanged.')
        if any(not isinstance(entry.get(field), list) or
               any(not isinstance(label, str) for label in entry[field]) for field in ('domains', 'tags')):
            raise ValueError('Invalid entry labels; backup unchanged.')
    # A second ID/revision scan catches same-count replacements and edits that
    # occurred behind the export cursor. REST pagination is not a transaction.
    verified = fetch_rows(url, key, ('id', 'revision'), reader)
    if [(e['id'], e['revision']) for e in entries] != [(e['id'], e['revision']) for e in verified]:
        raise ValueError('Vocabulary changed during export; retry the backup.')
    return entries


def markdown(value):
    """Keep contributed text literal, including Markdown and HTML payloads."""
    value = html.escape(str(value or ''), quote=False)
    return re.sub(r'([\\`*_{}\[\]()#+.!|>~-])', r'\\\1', value)


def source_link(value):
    try:
        parsed = urllib.parse.urlsplit(value)
        if parsed.scheme in ('http', 'https') and parsed.hostname and not parsed.username:
            return urllib.parse.quote(value, safe=':/?#@!$&\'*,;=+%')
    except ValueError:
        pass
    return ''


def render_markdown(entries):
    with_examples = sum(bool(entry.get('example', '').strip()) for entry in entries)
    groups = {pos: [] for pos in POSITIONS}
    for entry in entries:
        groups[entry['pos']].append(entry)
    lines = [
        '# 📚 PaperLex 社区词库', '',
        f'共 **{len(entries)} 个词条**，来自 Supabase 公开词库。每周一自动更新；可使用 GitHub 搜索或浏览器查找（Ctrl / ⌘ + F）。', '',
        f'其中 **{with_examples} 个词条有例句**，**{len(entries) - with_examples} 个词条待补例句**。统计随本次备份更新，不代表实时数量。', '',
        '本文件供查询与内容留存，历史版本可在 Git 提交记录中查看。包含公开词条内容，不含账号、私有历史或数据库权限配置。', '',
        ' · '.join(f'[{label}](#section-{pos})（{len(groups[pos])}）' for pos, label in POSITIONS.items()), '',
    ]
    for pos, label in POSITIONS.items():
        lines.extend([f'<a id="section-{pos}"></a>', '', f'## {label}', ''])
        for entry in sorted(groups[pos], key=lambda e: (e['term'].casefold(), e['id'])):
            domains = list(dict.fromkeys('计算机科学' if d in LEGACY_DOMAINS else d for d in entry['domains']))
            lines.extend([f'<a id="entry-{entry["id"]}"></a>', '', '### ' + markdown(entry['term']), '', markdown(entry['meaning']), ''])
            lines.extend(['**领域**：' + (' / '.join(map(markdown, domains)) or '待分类'), ''])
            if entry.get('tags'):
                lines.extend(['**标签**：' + ' / '.join(map(markdown, entry['tags'])), ''])
            if entry.get('example', '').strip():
                lines.extend(['**例句**', ''] + [('> ' + markdown(line)).rstrip() for line in entry['example'].splitlines()] + [''])
            source = ' · '.join(markdown(entry.get(field)) for field in ('source', 'source_venue', 'source_date') if entry.get(field))
            if source:
                lines.extend(['**出处**：' + source, ''])
            if entry.get('source_location'):
                lines.extend(['**原文位置**：' + markdown(entry['source_location']), ''])
            url = entry.get('source_url', '')
            safe = source_link(url)
            if safe:
                lines.extend([f'[查看来源]({safe})', ''])
            elif url:
                lines.extend(['**来源链接（原始文本）**：' + markdown(url), ''])
            if entry.get('author_name'):
                lines.extend(['**贡献者**：' + markdown(entry['author_name']), ''])
            lines.extend(['<details>', '<summary>记录信息</summary>', '', f'- ID：`{entry["id"]}`'])
            for field, title in (('created_at', '创建时间'), ('updated_at', '更新时间'), ('revision', '修订版本'), ('provenance', '导入来源')):
                if entry.get(field) is not None:
                    lines.append(f'- {title}：{markdown(entry[field])}')
            lines.extend(['', '</details>', ''])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'backups/vocabulary.md')
    args = parser.parse_args()
    try:
        content = render_markdown(fetch_entries(*configuration()))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.output.exists() and args.output.read_text(encoding='utf-8') == content:
            print('Public vocabulary is unchanged.')
            return
        temporary = args.output.with_suffix('.md.tmp')
        temporary.write_text(content, encoding='utf-8')
        temporary.replace(args.output)
        print('Public vocabulary Markdown backup written.')
    except (ValueError, OSError) as error:
        print(f'Backup failed: {error}', file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
