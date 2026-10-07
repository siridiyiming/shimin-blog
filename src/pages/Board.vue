<script setup>
import { MessageCircle } from '@lucide/vue';
import Comments from '../components/Comments.vue';
</script>
<template><div class="board-page"><header class="page-heading"><div class="eyebrow">SAY HELLO</div><h1>留下一点声音<span>✳</span></h1><p>一个想法、一句问候，或者一个建议。<br/>很高兴在这里遇见你。</p></header><div class="board-intro"><MessageCircle :size="23"/><p>这里是公开的留言空间。友善交流，尊重彼此，也请保护自己的隐私。</p></div><section class="board-sheet"><Comments/></section></div></template>
