<script setup>
import { watch, onBeforeUnmount } from 'vue';
import { useEditor, EditorContent } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import Image from '@tiptap/extension-image';
import { api } from '../api';
const props = defineProps({ modelValue: String });
const emit = defineEmits(['update:modelValue', 'error']);
const editor = useEditor({ extensions: [StarterKit.configure({ heading: { levels:[2,3,4] }, link: { openOnClick:false } }), Image], content: props.modelValue || '', editorProps:{ attributes:{ class:'prose editing-body', 'aria-label':'正文编辑器' } }, onUpdate:({editor}) => emit('update:modelValue',editor.getHTML()) });
watch(() => props.modelValue, value => { if (editor.value && value !== editor.value.getHTML()) editor.value.commands.setContent(value || '', { emitUpdate:false }); });
onBeforeUnmount(() => editor.value?.destroy());
function setLink() { const url = prompt('输入 HTTP 或 HTTPS 链接', editor.value.getAttributes('link').href || 'https://'); if (url === null) return; if (!url) editor.value.chain().focus().unsetLink().run(); else if (/^https?:\/\//i.test(url)) editor.value.chain().focus().setLink({href:url}).run(); else emit('error','链接必须使用 HTTP 或 HTTPS'); }
async function addImage(event) { const file = event.target.files?.[0]; if (!file) return; const form = new FormData(); form.append('file', file); try { const data = await api('/admin/media',{ method:'POST',body:form }); editor.value.chain().focus().setImage({src:data.url,alt:file.name}).run(); } catch(e) { emit('error',e.message); } event.target.value = ''; }
</script>
<template><div class="rich-editor"><div v-if="editor" class="editor-toolbar"><button type="button" :class="{ selected:editor.isActive('bold') }" @click="editor.chain().focus().toggleBold().run()"><b>粗体</b></button><button type="button" @click="editor.chain().focus().toggleItalic().run()"><i>斜体</i></button><button type="button" @click="editor.chain().focus().toggleHeading({level:2}).run()">标题</button><button type="button" @click="editor.chain().focus().toggleHeading({level:3}).run()">小标题</button><button type="button" @click="editor.chain().focus().toggleBulletList().run()">列表</button><button type="button" @click="editor.chain().focus().toggleBlockquote().run()">引用</button><button type="button" @click="editor.chain().focus().toggleCodeBlock().run()">代码块</button><button type="button" @click="setLink">链接</button><label class="toolbar-upload">图片<input type="file" accept="image/png,image/jpeg,image/webp" @change="addImage"/></label><button type="button" aria-label="撤销" @click="editor.chain().focus().undo().run()">↶</button></div><EditorContent :editor="editor"/></div></template>
