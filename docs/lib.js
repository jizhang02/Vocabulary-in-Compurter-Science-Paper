export const POS = {verb:"动词","adjective-adverb":"形容词 / 副词",noun:"名词",phrase:"短语"};
export const DOMAINS = ["通用","计算机科学","机器学习","计算机视觉","自然语言处理","医学","数学"];
export const escapeHtml = (text = "") => String(text).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
export const normalize = text => String(text ?? "").normalize("NFKC").toLocaleLowerCase().trim();
export function tagsFrom(text) {
  const values = [...new Set(text.split(/[,，]/).map(x => x.trim()).filter(Boolean))];
  if (values.length > 12 || values.some(x => x.length > 40)) throw new Error("每组最多 12 个标签，每个标签最多 40 字。");
  return values;
}
export function safeUrl(value) {
  try { const url = new URL(value); return ["http:","https:"].includes(url.protocol) ? url.href : ""; } catch { return ""; }
}
export function canEdit(entry, user, admin) { return Boolean(user && (admin || entry.owner_id === user.id)); }
export function filterEntries(entries, filters, user) {
  const terms = normalize(filters.query).split(/\s+/).filter(Boolean);
  return entries.filter(entry => {
    const haystack = normalize([entry.term,entry.meaning,entry.example,entry.source,entry.source_venue,entry.source_date,entry.source_location,...entry.domains,...entry.tags].join(" "));
    return terms.every(t => haystack.includes(t)) && (!filters.pos.size || filters.pos.has(entry.pos)) &&
      (!filters.domains.size || entry.domains.some(d => filters.domains.has(d))) &&
      (!filters.mine || Boolean(user && entry.owner_id === user.id));
  });
}

// Keep quotations as plain text in storage; escape every displayed fragment.
export function highlightExample(entry) {
  const text = String(entry.example ?? "");
  const aliases = {
    propell: "propel", jusity: "justify", interwine: "intertwine",
    compell: "compel", indistiguishable: "indistinguishable", mimick: "mimic",
    lever: "leverage", "w.r.t.with respect to": "with respect to",
    "a.k.a also known as": "also known as", "e.g for example": "for example",
    "i.e in other words": "in other words", "posteriori probability": "posterior probability",
    "herein this work": "in this work", "presumably speaking": "presumably"
  };
  const term = String(entry.term ?? "").trim();
  if (!term) return escapeHtml(text);
  const literal = value => value.split(/[\s\-–—‑−]+/u)
    .map(part => part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("[\\s\\-–—‑−]+");
  let source = literal(aliases[term] || term);
  if (term === "from...perspecitve") source = "from(?:[\\s\\-]+[\\p{L}\\p{N}_]+){0,6}[\\s\\-]+perspective";
  if (term === "pit against") source = "pit(?:[\\s\\-]+[\\p{L}\\p{N}_]+){0,7}[\\s\\-]+against";
  const matches = new RegExp("(?<![\\p{L}\\p{N}_])(?:" + source + ")(?![\\p{L}\\p{N}_])", "giu");
  let result = "", end = 0;
  for (const match of text.matchAll(matches)) {
    result += escapeHtml(text.slice(end, match.index));
    result += '<strong class="example-target">' + escapeHtml(match[0]) + '</strong>';
    end = match.index + match[0].length;
  }
  return result + escapeHtml(text.slice(end));
}

export const termKey = value => String(value ?? "").normalize("NFKC").toLowerCase().replace(/\s+/gu, " ").trim();
