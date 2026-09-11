import { POS, DOMAINS, escapeHtml as h, tagsFrom, safeUrl, canEdit, filterEntries, highlightExample } from "./lib.js";

const POS_SHORT = {verb:"v", "adjective-adverb":"adj/adv", noun:"n", phrase:"phr"};

const authorNickname = entry => entry.author_name === "Jing Zhang · 原始词表" ? "Jing Zhang" : (entry.author_name || "社区读者");
const isAuthored = entry => entry.source_venue === "自拟例句";
const $ = selector => document.querySelector(selector);
const state = { entries: [], mine: false, user: null, admin: false, client: null, online: false, page: 1, pageSize: 18, editing: null, authEpoch: 0 };
const config = window.VOCAB_CONFIG || {};
let toastTimer;
function toast(message) { $("#toast").textContent = message; $("#toast").hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $("#toast").hidden = true, 5000); }
function status(message, online = false) { $("#connection-status").textContent = message; $("#connection-status").classList.toggle("online", online); }
function filters() {
  return {query: $("#search").value, pos: new Set([...document.querySelectorAll("[name=filter-pos]:checked")].map(x => x.value)), domains: new Set([...document.querySelectorAll("[name=filter-domain]:checked")].map(x => x.value)), mine: state.mine};
}
function buildFilters() {
  const previous = filters();
  const counts = (key, value) => state.entries.filter(e => key === "pos" ? e.pos === value : e.domains.includes(value)).length;
  const checkbox = (name, value, label, count, selected) => `<label class="check"><input type="checkbox" name="filter-${name}" value="${h(value)}" ${selected ? "checked" : ""}>${h(label)}<small>${count}</small></label>`;
  $("#pos-filters").innerHTML = Object.entries(POS).map(([key,label]) => checkbox("pos",key,label,counts("pos",key),previous.pos.has(key))).join("");
  const domains = [...new Set([...DOMAINS,...state.entries.flatMap(e => e.domains)])];
  $("#domain-filters").innerHTML = domains.map(d => checkbox("domain",d,d,counts("domains",d),previous.domains.has(d))).join("");
  $("#total-stat").textContent = state.entries.length.toLocaleString();
  $("#example-stat").textContent = state.entries.filter(e => e.example).length.toLocaleString();
}
function selectedEntries() {
  const entries = filterEntries(state.entries, filters(), state.user);
  if ($("#sort").value === "random") {
    for (const entry of entries) {
      if (!randomOrder.has(entry.id)) randomOrder.set(entry.id, Math.random());
    }
    return entries.sort((a,b) => randomOrder.get(a.id) - randomOrder.get(b.id) || a.id.localeCompare(b.id));
  }
  return entries.sort((a,b) => $("#sort").value === "recent" ? (b.updated_at || "").localeCompare(a.updated_at || "") || a.term.localeCompare(b.term,"en") : a.term.localeCompare(b.term,"en") * ($("#sort").value === "za" ? -1 : 1));
}
function render() {
  const entries = selectedEntries();
  const pages = Math.max(1, Math.ceil(entries.length / state.pageSize));
  state.page = Math.min(state.page,pages);
  $("#result-count").textContent = `找到 ${entries.length} 个词条 · 共 ${state.entries.length} 个`;
  $("#cards").innerHTML = entries.slice((state.page-1)*state.pageSize,state.page*state.pageSize).map(e => `<article class="word-card"><button class="card-toggle card-expand" data-entry="${h(e.id)}" aria-label="展开 ${h(e.term)}" aria-haspopup="dialog" title="展开词条"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 9 3 3m0 6V3h6m6 12 6 6m-6 0h6v-6"/></svg></button><h3><span class="term-button">${h(e.term)}</span></h3><p class="card-meaning"><span>${h(e.meaning)}</span><span class="card-pos" title="${h(POS[e.pos] || e.pos)}">${h(POS_SHORT[e.pos] || e.pos)}</span></p>${e.example ? `<div class="card-example"><p>${highlightExample(e)}</p><span>${h([e.source_venue,e.source_date].filter(Boolean).join(" · ") || "出处待补全")}</span></div>` : ""}<div class="card-bottom"><div class="card-tags">${e.domains.slice(0,3).map(d => `<span class="tag">${h(d)}</span>`).join("")}</div><span class="card-author" title="贡献者：${h(authorNickname(e))}">${h(authorNickname(e))}</span></div></article>`).join("") || `<div class="empty"><h3>${filters().mine && !state.user ? "登录后查看你的贡献" : "还没有找到匹配的词汇"}</h3><p>试试其他关键词，或重置筛选条件。</p></div>`;
  $("#pagination").innerHTML = entries.length ? `<button data-page="${state.page-1}" ${state.page === 1 ? "disabled" : ""}>← 上一页</button><span>${state.page} / ${pages}</span><button data-page="${state.page+1}" ${state.page === pages ? "disabled" : ""}>下一页 →</button>` : "";
}
function refreshView() { state.page = 1; render(); }
function openEntry(id) {
  const e = state.entries.find(entry => entry.id === id);
  if (!e) return;
  const url = safeUrl(e.source_url);
  $("#entry-detail").innerHTML = `<div class="detail-heading"><h2 id="entry-title" class="detail-term">${h(e.term)}</h2><div class="detail-heading-meta"><p class="detail-meaning"><span>${h(e.meaning)}</span> <span class="card-pos" title="${h(POS[e.pos] || e.pos)}">${h(POS_SHORT[e.pos] || e.pos)}</span></p><div class="detail-tags">${[...e.domains,...e.tags].map(t=>`<span class="tag">${h(t)}</span>`).join("") || '<span class="tag">领域待分类</span>'}</div></div></div>${e.example ? `<section class="example-block" aria-labelledby="example-block-title"><h3 id="example-block-title">${isAuthored(e) ? "自拟例句" : "原文例句"}${isAuthored(e) ? '<span class="example-block-note">非论文原文</span>' : ""}</h3><blockquote class="detail-example">${highlightExample(e)}</blockquote></section>` : '<p class="form-note">这个词还没有例句，期待补充实际论文中的用法。</p>'}<dl class="citation-meta"><div class="citation-venue"><dt>${isAuthored(e) ? "例句类型" : "期刊 / 会议"}</dt><dd title="${h(e.source_venue || "待补充")}">${h(e.source_venue || "待补充")}</dd></div><div class="citation-date"><dt>${isAuthored(e) ? "编写日期" : "发表日期"}</dt><dd>${h(e.source_date || "待补充")}</dd></div><div><dt>${isAuthored(e) ? "例句标题" : "论文标题"}</dt><dd>${h(e.source || "待补充")}</dd></div></dl><div class="detail-footer">${url ? `<p class="detail-source"><a href="${h(url)}" target="_blank" rel="noopener noreferrer">查看原始来源 ↗</a></p>` : ""}<p class="detail-author">贡献者：${h(authorNickname(e))}${e.updated_at ? ` · 更新于 ${h(new Date(e.updated_at).toLocaleDateString("zh-CN"))}` : ""}</p></div>${state.online && canEdit(e,state.user,state.admin) ? `<div class="detail-actions"><button class="button primary" data-edit="${h(e.id)}">修改词汇</button><button class="button danger" data-delete="${h(e.id)}">删除词汇</button></div>` : ""}`;
  $("#entry-dialog").showModal();
}
function openAuth() {
  if (!state.client || !state.online) { toast("当前为只读词表。站点维护者连接社区数据库后，即可登录并贡献。"); return; }
  $("#auth-message").textContent = ""; $("#auth-dialog").showModal();
}
function openEditor(entry = null) {
  if (!state.online) { openAuth(); return; }
  if (!state.user) { openAuth(); return; }
  if (entry && !canEdit(entry,state.user,state.admin)) return;
  state.editing = entry;
  $("#editor").reset(); $("#editor-error").textContent = "";
  $("#editor-title").textContent = entry ? "修改词汇" : "添加词汇";
  for (const field of ["term","meaning","pos","domains","tags","example","source","source_venue","source_date","source_location","source_url"]) {
    const value = entry?.[field] ?? (field === "pos" ? "noun" : "");
    $("#editor").elements[field].value = Array.isArray(value) ? value.join("，") : value;
  }
  $("#entry-dialog").close(); $("#editor-dialog").showModal();
}
async function loadCloud() {
  const entries = [];
  // Keyset pagination remains correct when a project sets its API row cap below 1,000.
  let last = null;
  while (true) {
    let query = state.client.from("entries").select("*").order("id").limit(1000);
    if (last) query = query.gt("id",last);
    const {data,error} = await query;
    if (error) throw error;
    if (!data.length) break;
    entries.push(...data); last = data.at(-1).id;
  }
  state.entries = entries; state.online = true; buildFilters(); render();
  status("社区词库已连接 · 浏览无需登录，登录后可添加和管理自己的词汇。",true);
}
async function updateUser(user) {
  const epoch = ++state.authEpoch;
  const changed = state.user?.id !== user?.id;
  state.user = user; state.admin = false;
  if (changed) { $("#entry-dialog").close(); $("#editor-dialog").close(); }
  if (user) {
    const {data,error} = await state.client.rpc("is_admin");
    if (epoch !== state.authEpoch) return;
    state.admin = !error && data === true;
  }
  $("#auth-button").textContent = user ? `${state.admin ? "管理员" : "已登录"} · 退出` : "登录 / 注册";
  if (!user) state.mine = false;
  render();
}
async function saveEntry(event) {
  event.preventDefault();
  const button = $("#save-entry"); button.disabled = true; $("#editor-error").textContent = "";
  try {
    if (!state.online || !state.user) throw new Error("请先登录后再保存。");
    const form = new FormData(event.target);
    const row = Object.fromEntries(["term","meaning","pos","example","source","source_venue","source_date","source_location","source_url"].map(k => [k,form.get(k).trim()]));
    row.domains = tagsFrom(form.get("domains")); row.tags = tagsFrom(form.get("tags"));
    if (!row.term || !row.meaning) throw new Error("词汇和释义不能只包含空格。");
    if (row.source_date && !/^\d{4}(-(?:0[1-9]|1[0-2])(-(?:0[1-9]|[12]\d|3[01]))?)?$/.test(row.source_date)) throw new Error("发表日期请填写 YYYY、YYYY-MM 或 YYYY-MM-DD。");
    if (row.source_url && !safeUrl(row.source_url)) throw new Error("来源链接必须以 http:// 或 https:// 开头。");
    if (state.editing) {
      const {data,error} = await state.client.from("entries").update(row).eq("id",state.editing.id).eq("revision",state.editing.revision).select();
      if (error) throw error;
      if (!data.length) throw new Error("词条已被其他人修改或删除，或你已无编辑权限。请关闭表单并刷新后重试；可先复制当前内容。");
    } else {
      row.owner_id = state.user.id;
      const metadata = state.user.user_metadata || {};
      row.author_name = String(metadata.user_name || metadata.preferred_username || "社区读者").slice(0,100);
      const {error} = await state.client.from("entries").insert(row);
      if (error) throw error;
    }
    $("#editor-dialog").close(); toast("词汇已保存，感谢你的贡献。");
    try { await loadCloud(); } catch { status("保存成功，但列表刷新失败。请刷新网页获取最新词库。"); }
  } catch (error) { $("#editor-error").textContent = error.message || "保存失败，请稍后重试。"; }
  finally { button.disabled = false; }
}
async function deleteEntry(id,button) {
  const e = state.entries.find(x => x.id === id);
  if (!e || !state.online || !canEdit(e,state.user,state.admin)) return;
  if (!confirm(`确定删除「${e.term}」？删除后将从公共词库移除。`)) return;
  button.disabled = true;
  try {
    const {data,error} = await state.client.from("entries").delete().eq("id",id).eq("revision",e.revision).select();
    if (error) throw error;
    if (!data.length) throw new Error("词条已变化或权限不足，请刷新后重试。");
    $("#entry-dialog").close(); toast("词汇已删除。");
    try { await loadCloud(); } catch { status("删除成功，但列表刷新失败。请刷新网页获取最新词库。"); }
  } catch (error) { toast(error.message); } finally { button.disabled = false; }
}

$("#editor").elements.pos.innerHTML = Object.entries(POS).map(([key,value])=>`<option value="${key}">${value}</option>`).join("");
document.addEventListener("click",event => {
  const close = event.target.closest("[data-close]"); if (close) close.closest("dialog").close();
  const entry = event.target.closest("[data-entry]"); if (entry) openEntry(entry.dataset.entry);
  const edit = event.target.closest("[data-edit]"); if (edit) openEditor(state.entries.find(e=>e.id === edit.dataset.edit));
  const del = event.target.closest("[data-delete]"); if (del) void deleteEntry(del.dataset.delete,del);
  const page = event.target.closest("[data-page]"); if (page) { state.page = Number(page.dataset.page); render(); $("#library").scrollIntoView({behavior:"instant"}); }
});
$("#search").addEventListener("input",refreshView);
const randomOrder = new Map();
$("#sort").addEventListener("change",() => {
  if ($("#sort").value === "random") randomOrder.clear();
  refreshView();
});
$(".filters").addEventListener("change",refreshView);
$("#reset").onclick = () => { state.mine = false; $("#search").value = ""; document.querySelectorAll(".filters input").forEach(x=>x.checked=false); refreshView(); };
$("#add-entry").onclick = () => openEditor();
$("#my-contributions").onclick = () => {
  if (!state.user) { openAuth(); return; }
  $("#search").value = "";
  document.querySelectorAll(".filters input").forEach(input => input.checked = false);
  state.mine = true;
  refreshView();
  $("#library").scrollIntoView({behavior:"smooth",block:"start"});
};
$("#random-entry").onclick = () => { const entries = selectedEntries(); if (entries.length) openEntry(entries[Math.floor(Math.random()*entries.length)].id); else toast("当前筛选没有词汇，可以先重置筛选。"); };
for (const view of ["grid","list"]) $(`#${view}-view`).onclick = () => { $("#cards").classList.toggle("list-mode",view === "list"); for (const key of ["grid","list"]) { $(`#${key}-view`).classList.toggle("selected",key === view); $(`#${key}-view`).setAttribute("aria-pressed",String(key === view)); } };
document.addEventListener("keydown",event => { if (event.key === "/" && !document.querySelector("dialog[open]") && !["INPUT","TEXTAREA","SELECT"].includes(document.activeElement.tagName)) { event.preventDefault(); $("#search").focus(); } });
$("#editor").addEventListener("submit",saveEntry);
$("#auth-button").onclick = async () => {
  if (!state.user) { openAuth(); return; }
  try { const {error} = await state.client.auth.signOut(); if (error) throw error; await updateUser(null); toast("已退出登录。"); } catch (error) { toast(error.message); }
};
$("#github-login").onclick = async () => {
  try {
    const {error} = await state.client.auth.signInWithOAuth({provider:"github",options:{redirectTo:new URL("./",location.href).href}});
    if (error) throw error;
  } catch (error) { $("#auth-message").textContent = error.message; }
};
let otpEmail = "";
$("#email-form").onsubmit = async event => {
  event.preventDefault(); const button = event.target.querySelector("button"); button.disabled = true;
  try {
    const email = $("#email").value.trim();
    const {error} = await state.client.auth.signInWithOtp({email,options:{shouldCreateUser:true}});
    if (error) throw error;
    otpEmail = email; $("#otp-form").hidden = false; $("#auth-message").textContent = "验证码已发送，请检查邮箱（包括垃圾邮件）。"; $("#otp").focus();
  } catch (error) { $("#auth-message").textContent = error.message; } finally { button.disabled = false; }
};
$("#otp-form").onsubmit = async event => {
  event.preventDefault(); const button = event.target.querySelector("button"); button.disabled = true;
  try {
    const {error} = await state.client.auth.verifyOtp({email:otpEmail,token:$("#otp").value.trim(),type:"email"});
    if (error) throw error;
    $("#auth-dialog").close(); toast("登录成功，现在可以添加词汇了。");
  } catch (error) { $("#auth-message").textContent = error.message; } finally { button.disabled = false; }
};

async function start() {
  try {
    const response = await fetch(new URL("./data/vocabulary.json",import.meta.url));
    if (!response.ok) throw new Error("词表加载失败");
    state.entries = await response.json(); buildFilters(); render();
    status("当前展示原始词表，只读浏览可用。社区登录与编辑将在站点完成连接后开放。");
  } catch { status("原始词表加载失败，请通过 HTTP 服务访问或刷新重试。"); }
  if (!config.supabaseUrl || !config.supabasePublishableKey) return;
  try {
    status("正在连接社区词库…");
    const {createClient} = await import("https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.57.4/+esm");
    state.client = createClient(config.supabaseUrl,config.supabasePublishableKey,{auth:{flowType:"pkce",detectSessionInUrl:true,persistSession:true,autoRefreshToken:true}});
    state.client.auth.onAuthStateChange((_event,session) => { setTimeout(() => void updateUser(session?.user || null),0); });
    const {data,error} = await state.client.auth.getSession();
    if (error) throw error;
    await updateUser(data.session?.user || null); await loadCloud();
  } catch (error) { state.online = false; status(`社区连接失败，当前仅浏览原始词表，编辑暂不可用。${error.message || "请稍后刷新重试。"}`); }
}
void start();
