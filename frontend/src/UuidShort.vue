<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
const props = withDefaults(defineProps<{ id: string; full?: boolean }>(), { full: false })
const copied = ref(false)
async function copy() {
  try {
    await navigator.clipboard.writeText(props.id)
    copied.value = true
    ElMessage.success('编号已复制')
    setTimeout(() => (copied.value = false), 1600)
  } catch {
    ElMessage.warning('复制失败，请手动选择编号')
  }
}
</script>
<template>
  <span class="uuid" :class="{ full }" :title="id">
    <span class="uuid-text">{{ full ? id : id.slice(0, 8) + '…' }}</span>
    <button class="uuid-copy" type="button" :aria-label="'复制编号 ' + id" @click.stop="copy">{{ copied ? '已复制' : '复制' }}</button>
  </span>
</template>
<style scoped>
.uuid { display: inline-flex; align-items: center; gap: 6px; max-width: 100%; }
.uuid-text { font-family: ui-monospace, "Cascadia Mono", Consolas, monospace; font-size: 12px; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.uuid.full .uuid-text { white-space: normal; overflow-wrap: anywhere; }
.uuid-copy { border: 0; background: transparent; color: var(--accent); font-size: 11px; padding: 0 2px; cursor: pointer; border-radius: 4px; flex-shrink: 0; opacity: 0; transition: opacity .12s; }
.uuid:hover .uuid-copy, .uuid-copy:focus-visible { opacity: 1; }
.uuid-copy:hover { text-decoration: underline; }
</style>
