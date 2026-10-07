<script setup>
import { ref, watch } from 'vue';
import { MessageCircle, Send, CornerDownRight } from '@lucide/vue';
import { api, dateLabel, site } from '../api';
const props = defineProps({ contentId: { type: String, default: '' } });
const emit = defineEmits(['posted']);
const items = ref([]), loading = ref(false), error = ref(''), success = ref(''), page = ref(1), more = ref(false), sending = ref(false), reply = ref(null), body = ref('');
const nickname = ref(localStorage.getItem('blog-nickname') || '');
async function load(append = false) { loading.value = true; error.value = ''; try { const result = await api(`/comments?contentId=${props.contentId}&page=${page.value}`); items.value = append ? [...items.value, ...result.items] : result.items; more.value = result.hasMore; } catch (e) { error.value = e.message; } finally { loading.value = false; } }
async function send() { sending.value = true; error.value = ''; success.value = ''; try { await api('/comments', { method: 'POST', body: { contentId: props.contentId || null, nickname: nickname.value, body: body.value, replyTo: reply.value?.id || null } }); localStorage.setItem('blog-nickname', nickname.value); body.value = ''; reply.value = null; page.value = 1; success.value = '已发送，感谢留下你的想法。'; emit('posted'); await load(); } catch (e) { error.value = e.message; } finally { sending.value = false; } }
function selectReply(item) { reply.value = item; document.getElementById('comment-input-' + props.contentId)?.focus(); }
watch(() => props.contentId, () => { page.value = 1; items.value = []; load(); }, { immediate: true });
</script>
<template>
  <section class="comments">
    <h3><MessageCircle :size="19"/>交流一下</h3>
    <form class="comment-form" @submit.prevent="send">
      <label>昵称 <span v-if="site.isAdmin" class="badge">站长身份</span><input v-model="nickname" placeholder="怎么称呼你？" maxlength="40" required autocomplete="nickname"/></label>
      <div v-if="reply" class="reply-target">回复 {{ reply.nickname }}<button type="button" @click="reply = null">取消回复</button></div>
      <label class="sr-only" :for="'comment-input-' + contentId">评论内容</label><textarea :id="'comment-input-' + contentId" v-model="body" placeholder="分享你的想法，让交流从这里开始…" rows="4" maxlength="2000" required></textarea>
      <div class="form-bottom"><small>我想分享想法或工具~<br/>我想提一些建议~</small><button class="button" :disabled="sending"><Send :size="15"/>{{ sending ? '发送中…' : '发送留言' }}</button></div>
    </form>
    <p v-if="error" class="error" role="alert">{{ error }} <button type="button" @click="load()">重新加载评论</button></p><p v-if="success" class="success" role="status">{{ success }}</p>
    <div v-if="loading && !items.length" class="empty-small">正在加载评论…</div>
    <div v-else-if="!items.length" class="empty-small">这里还很安静，欢迎留下第一条真实的想法。</div>
    <article v-for="item in items" :key="item.id" class="comment-thread">
      <div class="comment-head"><span class="comment-avatar">{{ item.nickname.slice(0,1) }}</span><strong>{{ item.nickname }}</strong><span v-if="item.is_admin" class="badge">站长</span><time>{{ dateLabel(item.created_at) }}</time></div><p :class="{ muted: item.deleted }">{{ item.body }}</p><button v-if="!item.deleted" class="text-button" @click="selectReply(item)">回复</button>
      <div v-for="child in item.replies" :key="child.id" class="comment-reply"><div class="comment-head"><CornerDownRight :size="15"/><strong>{{ child.nickname }}</strong><span v-if="child.is_admin" class="badge">站长</span><time>{{ dateLabel(child.created_at) }}</time></div><blockquote v-if="child.quote">回复 {{ child.quote.nickname }}：{{ child.quote.body }}</blockquote><p>{{ child.body }}</p><button class="text-button" @click="selectReply(child)">回复</button></div>
    </article>
    <button v-if="more" class="button secondary load-more" :disabled="loading" @click="page++; load(true)">加载更多评论</button>
  </section>
</template>
