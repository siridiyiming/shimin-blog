<script setup>
import { ref } from 'vue';
import { Heart, MessageCircle, ArrowUpRight, ArrowRight, ChevronDown, Link, FileText, Lightbulb } from '@lucide/vue';
import { api, dateLabel } from '../api';
import Comments from './Comments.vue';
import RichBody from './RichBody.vue';
const props = defineProps({ item: Object, compact: Boolean });
const expanded = ref(false), busy = ref(false), error = ref(''), copied = ref(false);
async function like() { busy.value = true; error.value = ''; try { Object.assign(props.item, await api(`/contents/${props.item.id}/like`, { method: 'PUT', body: { liked: !props.item.liked } })); } catch(e) { error.value = e.message; } finally { busy.value = false; } }
async function share() { try { await navigator.clipboard.writeText(location.origin + '/content/' + props.item.id); copied.value = true; } catch { error.value = '请打开详情页后复制地址栏链接'; } }
</script>
<template>
  <article :id="'item-'+item.id" :class="['content-card', 'type-'+item.type, { compact, expanded }]">
    <RouterLink v-if="item.cover && ['game','article'].includes(item.type)" :to="'/content/'+item.id" class="card-cover"><img :src="item.cover" :alt="item.title+'封面'" loading="lazy"/><span v-if="item.type==='game'" class="cover-label">{{ item.device || '探索游戏' }}</span><span class="cover-arrow"><ArrowUpRight :size="20"/></span></RouterLink>
    <div class="card-content">
      <div class="card-meta"><span :class="['pill', item.type]">{{ item.type==='article' ? '长文章' : item.type==='note' ? '知识卡片' : item.category || (item.type==='game' ? '游戏' : '工具') }}</span><span v-if="item.tags.includes('占位示例')" class="sample-label">占位示例</span><time v-if="item.show_published_at !== false && item.published_at">{{ dateLabel(item.published_at) }}</time></div>
      <div v-if="item.type==='tool'" class="tool-heading"><img v-if="item.cover" :src="item.cover" alt="" loading="lazy"/><span v-else class="tool-monogram">{{ item.title.slice(0,1) }}</span><h3>{{ item.title }}</h3><a :href="item.url" target="_blank" rel="noopener noreferrer" :aria-label="'访问'+item.title" class="icon-button"><ArrowUpRight :size="19"/></a></div>
      <h3 v-else><Lightbulb v-if="item.type==='note'" :size="19"/><RouterLink :to="'/content/'+item.id">{{ item.title }}</RouterLink></h3>
      <p v-if="item.summary" class="card-summary">{{ item.summary }}</p>
      <div v-if="item.tags.some(t=>t!=='占位示例')" class="card-tags"><span v-for="tag in item.tags.filter(t=>t!=='占位示例')" :key="tag"># {{ tag }}</span></div>
      <div class="card-actions"><button :class="{ liked: item.liked }" :aria-label="item.liked ? '取消点赞' : '点赞'" :aria-pressed="item.liked" :disabled="busy" @click="like"><Heart :size="16" :fill="item.liked ? 'currentColor' : 'none'"/>{{ item.like_count }}</button><button v-if="['tool','note'].includes(item.type)" @click="expanded=!expanded"><MessageCircle :size="16"/>{{ item.comment_count }}<span>{{ expanded ? '收起' : '展开交流' }}</span></button><RouterLink v-else :to="'/content/'+item.id"><MessageCircle :size="16"/>{{ item.comment_count }}</RouterLink><button v-if="item.type==='note'" class="action-end" @click="share"><Link :size="15"/>{{ copied ? '已复制' : '分享' }}</button><RouterLink v-if="item.type==='game'" class="action-end" :to="'/content/'+item.id">了解游戏 <ArrowRight :size="14"/></RouterLink><a v-if="item.type==='tool'" class="action-end" :href="item.url" target="_blank" rel="noopener noreferrer">访问 <ArrowUpRight :size="14"/></a></div>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div v-if="expanded" class="inline-detail"><RichBody v-if="item.type==='note'" :html="item.body"/><a v-if="item.type==='note' && item.url" :href="item.url" target="_blank" rel="noopener noreferrer" class="text-link">相关链接 ↗</a><img v-if="item.type==='note' && item.cover" class="inline-image" :src="item.cover" alt="卡片配图" loading="lazy"/><Comments :content-id="item.id" @posted="item.comment_count++"/></div>
    </div>
  </article>
</template>
