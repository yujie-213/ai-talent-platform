<script setup lang="ts">
// 空态：不只是一句描述，而是告诉用户下一步做什么。
import AppIcon from './AppIcon.vue'
withDefaults(defineProps<{ title: string; hint?: string; actionLabel?: string; icon?: string }>(), { icon: 'file' })
const emit = defineEmits<{ action: [] }>()
</script>
<template>
  <div class="empty-state">
    <span class="empty-icon"><AppIcon :name="icon" /></span>
    <p class="empty-title">{{ title }}</p>
    <p v-if="hint" class="empty-hint">{{ hint }}</p>
    <el-button v-if="actionLabel" type="primary" @click="emit('action')">{{ actionLabel }}</el-button>
  </div>
</template>
<style scoped>
.empty-state { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 44px 20px; text-align: center; }
.empty-icon { width: 44px; height: 44px; border-radius: 12px; display: grid; place-items: center; background: var(--accent-soft); color: var(--accent); }
.empty-icon :deep(svg) { width: 22px; height: 22px; }
.empty-title { margin: 4px 0 0; font-size: 14px; font-weight: 600; color: var(--text); }
.empty-hint { margin: 0; font-size: 12px; color: var(--text-tertiary); max-width: 420px; line-height: 1.8; }
.empty-state .el-button { margin-top: 8px; }
</style>
