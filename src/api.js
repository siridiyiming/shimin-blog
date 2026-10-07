import { reactive } from 'vue';
export const site = reactive({ settings: {}, taxonomies: [], isAdmin: false, ready: false });
export const listCache = new Map();
export async function api(path, options = {}) {
  const headers = { 'X-Blog-Request': '1', ...options.headers };
  if (options.body && !(options.body instanceof FormData)) { headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(options.body); }
  let response;
  try { response = await fetch('/api' + path, { ...options, headers, credentials: 'same-origin' }); }
  catch { throw new Error('网络连接失败，请检查网络后重试；你的输入仍然保留。'); }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) { const error = new Error(data.error || '请求失败，请稍后重试'); error.status = response.status; throw error; }
  return data;
}
export async function loadSite() { Object.assign(site, await api('/bootstrap'), { ready: true }); document.title = `${site.settings.name} · 创作与分享`; }
export const dateLabel = value => new Date(value * 1000).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' });
export const typeLabels = { game: '游戏', article: '长文章', note: '知识卡片', tool: '工具' };
