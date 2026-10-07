<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { ArrowUpRight, ChevronLeft, ChevronRight, X } from '@lucide/vue';

const props = defineProps({ slides: { type: Array, default: () => [] } });
const index = ref(0), open = ref(false), paused = ref(false);
const current = computed(() => props.slides[index.value]);
let timer;
function move(step) { index.value = (index.value + step + props.slides.length) % props.slides.length; }
function keydown(event) {
  if (event.key === 'Escape') open.value = false;
  if (open.value && event.key === 'ArrowLeft' && props.slides.length > 1) move(-1);
  if (open.value && event.key === 'ArrowRight' && props.slides.length > 1) move(1);
}
watch(() => props.slides.length, () => { index.value = 0; open.value = false; });
onMounted(() => {
  timer = window.setInterval(() => { if (!open.value && !paused.value && props.slides.length > 1) move(1); }, 5000);
  window.addEventListener('keydown', keydown);
});
onUnmounted(() => { window.clearInterval(timer); window.removeEventListener('keydown', keydown); });
</script>

<template>
  <section v-if="current" class="home-carousel" aria-label="首页轮播图" @mouseenter="paused=true" @mouseleave="paused=false" @focusin="paused=true" @focusout="paused=false">
    <a v-if="current.action==='link'" class="carousel-slide" :href="current.url" target="_blank" rel="noopener noreferrer" :aria-label="current.title || '打开轮播图链接'">
      <img :src="current.image" :alt="current.title || '轮播图片'"/><span v-if="current.title" class="carousel-title">{{ current.title }}</span><span class="carousel-hint">查看详情 <ArrowUpRight :size="15"/></span>
    </a>
    <button v-else type="button" class="carousel-slide" :aria-label="`放大查看${current.title || '轮播图片'}`" @click="open=true">
      <img :src="current.image" :alt="current.title || '轮播图片'"/><span v-if="current.title" class="carousel-title">{{ current.title }}</span><span class="carousel-hint">点击查看大图</span>
    </button>
    <template v-if="slides.length>1"><button type="button" class="carousel-arrow previous" aria-label="上一张" @click="move(-1)"><ChevronLeft :size="20"/></button><button type="button" class="carousel-arrow next" aria-label="下一张" @click="move(1)"><ChevronRight :size="20"/></button><div class="carousel-dots" aria-label="选择轮播图"><button v-for="(slide,i) in slides" :key="i" type="button" :class="{active:i===index}" :aria-label="`第 ${i+1} 张`" :aria-current="i===index ? 'true' : undefined" @click="index=i"></button></div></template>
  </section>
  <Teleport to="body"><div v-if="open && current" class="carousel-lightbox" role="presentation" @click.self="open=false"><div class="carousel-lightbox-panel" role="dialog" aria-modal="true" :aria-label="current.title || '轮播图片预览'"><button type="button" class="carousel-close" aria-label="关闭大图" @click="open=false"><X :size="22"/></button><img :src="current.image" :alt="current.title || '轮播图片'"/><div class="carousel-lightbox-footer"><strong>{{ current.title }}</strong><a v-if="current.action==='preview_link'" class="button" :href="current.url" target="_blank" rel="noopener noreferrer">查看详情 <ArrowUpRight :size="16"/></a></div></div></div></Teleport>
</template>
