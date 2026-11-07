<script setup lang="ts">
import { computed } from 'vue'
const props = withDefaults(defineProps<{ state: string; label?: string }>(), { label: '' })
// 全站唯一的状态映射：同一状态在所有页面同文同色。
const table: Record<string, { label: string; tone: 'ok' | 'wait' | 'progress' | 'err' | 'muted' }> = {
  queued: { label: '待处理', tone: 'wait' },
  running: { label: '处理中', tone: 'progress' },
  succeeded: { label: '成功', tone: 'ok' },
  success: { label: '成功', tone: 'ok' },
  completed: { label: '已完成', tone: 'ok' },
  failed: { label: '失败', tone: 'err' },
  rejected: { label: '上传失败', tone: 'err' },
  denied: { label: '已拒绝', tone: 'err' },
  draft: { label: '草稿', tone: 'muted' },
  active: { label: '有效', tone: 'ok' },
  disabled: { label: '已停用', tone: 'muted' },
  pending: { label: '待参与', tone: 'muted' },
  answering: { label: '作答中', tone: 'progress' },
  submitted: { label: '待评分', tone: 'wait' },
}
const entry = computed(() => table[props.state] || { label: props.state || '未知', tone: 'muted' as const })
const text = computed(() => props.label || entry.value.label)
</script>
<template>
  <span class="status-tag" :class="'tone-' + entry.tone"><span class="dot" aria-hidden="true" />{{ text }}</span>
</template>
<style scoped>
.status-tag { display: inline-flex; align-items: center; gap: 5px; height: 22px; padding: 0 8px; border-radius: 6px; font-size: 12px; line-height: 1; white-space: nowrap; }
.dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.tone-ok { background: #e7f6ef; color: #14715a; }
.tone-ok .dot { background: #1a9e6f; }
.tone-wait { background: #fbf3e3; color: #9a6a1c; }
.tone-wait .dot { background: #d99426; }
.tone-progress { background: var(--accent-soft); color: var(--accent); }
.tone-progress .dot { background: var(--accent); animation: pulse 1.2s ease-in-out infinite; }
.tone-err { background: #faeaea; color: #a93434; }
.tone-err .dot { background: #c0393f; }
.tone-muted { background: var(--surface-muted); color: var(--text-tertiary); }
.tone-muted .dot { background: var(--border-strong); }
@keyframes pulse { 50% { opacity: .35; } }
</style>
