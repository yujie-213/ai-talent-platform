<script setup lang="ts">
import { computed } from 'vue'
// 首字色块头像：颜色由姓名稳定推导，同一个人在任何页面颜色一致。
const props = withDefaults(defineProps<{ name: string; size?: number }>(), { size: 38 })
const palettes: [string, string][] = [
  ['#e3ecff', '#2f5bea'],
  ['#e0f5ef', '#12805c'],
  ['#f3e9ff', '#7a3fd1'],
  ['#fdeee0', '#b45f06'],
  ['#e6f4fb', '#0e7490'],
  ['#fbe8ef', '#b0336b'],
]
const index = computed(() => {
  let hash = 0
  for (const ch of props.name || ' ') hash = (hash * 31 + (ch.codePointAt(0) || 0)) >>> 0
  return hash % palettes.length
})
const pair = computed(() => palettes[index.value]!)
const initial = computed(() => (props.name || '？').trim().slice(0, 1))
</script>
<template>
  <span class="person-avatar" aria-hidden="true" :style="{ width: size + 'px', height: size + 'px', background: pair[0], color: pair[1], fontSize: Math.round(size * 0.42) + 'px', borderRadius: Math.round(size * 0.28) + 'px' }">{{ initial }}</span>
</template>
<style scoped>
.person-avatar { display: inline-grid; place-items: center; flex-shrink: 0; font-weight: 600; line-height: 1; user-select: none; }
</style>
