<script setup lang="ts">
// 统一页面骨架：标题 + 一句「给谁做什么」的用途说明 + 右侧唯一主操作区。
defineProps<{ title: string; subtitle?: string }>()
</script>
<template>
  <div class="page-header">
    <div class="page-header-text">
      <h1>{{ title }}</h1>
      <p v-if="subtitle" class="page-header-sub">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.default" class="page-header-actions"><slot /></div>
  </div>
</template>
<style scoped>
.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin: 0 0 16px; }
.page-header-text h1 { margin: 0; font-size: 20px; font-weight: 600; }
.page-header-sub { margin: 5px 0 0; font-size: 13px; color: var(--text-secondary); }
.page-header-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; padding-top: 2px; }
@media (max-width: 720px) { .page-header { flex-wrap: wrap; } }
</style>
