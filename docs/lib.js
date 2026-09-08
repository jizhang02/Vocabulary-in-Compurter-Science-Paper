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
    const haystack = normalize([entry.term,entry.meaning,entry.example,entry.source,...entry.domains,...entry.tags].join(" "));
    return terms.every(t => haystack.includes(t)) && (!filters.pos.size || filters.pos.has(entry.pos)) &&
      (!filters.domains.size || entry.domains.some(d => filters.domains.has(d))) &&
      (!filters.example || Boolean(entry.example)) && (!filters.mine || Boolean(user && entry.owner_id === user.id));
  });
}
