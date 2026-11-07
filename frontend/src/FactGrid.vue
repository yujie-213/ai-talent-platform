<script setup lang="ts">
// 结构化事实栅格：label 在上、值在下，替代「标签：值」平铺段落。
// 每个 key 对应一个同名插槽，未提供插槽时渲染纯文本 value。
// span：长内容（编号、长句）可跨列，避免把相邻字段挤窄。
defineProps<{ items: { key: string; label: string; value?: string; span?: number }[] }>()
</script>
<template>
  <dl class="fact-grid">
    <div v-for="item in items" :key="item.key" class="fact-cell" :style="{ gridColumn: item.span ? 'span ' + item.span : undefined }">
      <dt>{{ item.label }}</dt>
      <dd><slot :name="item.key" :item="item">{{ item.value ?? '—' }}</slot></dd>
    </div>
  </dl>
</template>
<style scoped>
.fact-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px 20px; margin: 0; }
.fact-cell { min-width: 0; }
.fact-cell dt { font-size: 12px; color: var(--text-tertiary); margin-bottom: 5px; }
.fact-cell dd { margin: 0; font-size: 13px; color: var(--text); font-weight: 500; min-width: 0; overflow-wrap: anywhere; }
</style>
