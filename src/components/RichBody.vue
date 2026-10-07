<script setup>
import { computed } from 'vue';
const props = defineProps({ html: { type: String, default: '' }, toc: Boolean });
const parsed = computed(() => {
  const doc = new DOMParser().parseFromString(props.html, 'text/html');
  const headings = [...doc.querySelectorAll('h2,h3,h4')].map((el, index) => { el.id = 'section-' + index; return { id: el.id, text: el.textContent }; });
  doc.querySelectorAll('a').forEach(el => { el.target = '_blank'; el.rel = 'noopener noreferrer'; });
  doc.querySelectorAll('img').forEach(el => { el.loading = 'lazy'; });
  return { html: doc.body.innerHTML, headings };
});
</script>
<template><div><aside v-if="toc && parsed.headings.length" class="toc"><strong>本文目录</strong><a v-for="h in parsed.headings" :key="h.id" :href="'#'+h.id">{{ h.text }}</a></aside><div class="prose" v-html="parsed.html"></div></div></template>
