<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { Home, Gamepad2, BookOpen, Wrench, MessageCircle, Search } from '@lucide/vue';
import { site, loadSite } from './api';
const route = useRoute();
const error = ref('');
const nav = [{ path: '/', label: '首页', icon: Home }, { path: '/games', label: '游戏', icon: Gamepad2 }, { path: '/knowledge', label: '知识', icon: BookOpen }, { path: '/tools', label: '工具', icon: Wrench }, { path: '/board', label: '留言', icon: MessageCircle }];
const isAdmin = computed(() => route.path.startsWith('/admin'));
async function init() { error.value = ''; try { await loadSite(); } catch (e) { error.value = e.message; } }
onMounted(init);
</script>
<template>
  <a class="skip-link" href="#main">跳到正文</a>
  <header class="site-header"><div class="header-inner">
    <RouterLink to="/" class="brand"><span class="brand-mark">柿<span></span></span><span>{{ site.settings.name || '一码当先小柿民博客' }}<small>创作 · 记录 · 分享</small></span></RouterLink>
    <nav class="desktop-nav" aria-label="主导航"><RouterLink v-for="item in nav" :key="item.path" :to="item.path" :class="{ active: route.path === item.path }"><component :is="item.icon" :size="17" />{{ item.label }}</RouterLink></nav>
    <RouterLink to="/search" class="header-search" aria-label="全站搜索"><Search :size="19"/><span>发现点什么</span><kbd>⌕</kbd></RouterLink>
  </div></header>
  <main id="main" :class="['main-wrap', { 'admin-wrap': isAdmin }]">
    <div v-if="error" class="state-panel" role="alert"><h2>暂时无法加载站点</h2><p>{{ error }}</p><button class="button" @click="init">重新加载</button></div>
    <RouterView v-else-if="site.ready" />
    <div v-else class="state-panel" aria-live="polite">正在加载你的下一次发现…</div>
  </main>
  <footer class="site-footer"><span>© {{ new Date().getFullYear() }} {{ site.settings.name || '一码当先小柿民博客' }}<span class="footer-note"> · 保持好奇，慢慢生长。</span></span></footer>
  <nav v-if="!isAdmin" class="mobile-nav" aria-label="底部导航"><RouterLink v-for="item in nav" :key="item.path" :to="item.path" :class="{ active: route.path === item.path }"><component :is="item.icon" :size="21"/><span>{{ item.label }}</span></RouterLink></nav>
</template>
