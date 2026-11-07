<script setup lang="ts">
import { computed } from 'vue'
// 匹配分的视觉参照点：圆环只表达本次范围内的相对排序位置，不是能力评分或录用概率。
const props = withDefaults(defineProps<{ score: number | null | undefined; size?: number; pending?: boolean }>(), { size: 40 })
const clamped = computed(() => props.score == null ? null : Math.max(0, Math.min(100, Math.round(props.score))))
const level = computed(() => clamped.value == null ? 'none' : clamped.value >= 80 ? 'high' : clamped.value >= 50 ? 'mid' : 'low')
const stroke = 3.5
const radius = computed(() => (props.size - stroke) / 2)
const perimeter = computed(() => 2 * Math.PI * radius.value)
const dash = computed(() => clamped.value == null ? 0 : perimeter.value * (clamped.value / 100))
</script>
<template>
  <span class="score-ring" :class="[level, { pending }]" :style="{ width: size + 'px', height: size + 'px' }" role="img" :aria-label="clamped == null ? '暂无匹配分' : `匹配排序参考 ${clamped} 分`" :title="clamped == null ? '暂无匹配分' : `本次范围内的排序参考值 ${clamped}，不代表能力或录用概率`">
    <svg :width="size" :height="size" aria-hidden="true">
      <circle class="ring-track" :cx="size / 2" :cy="size / 2" :r="radius" fill="none" :stroke-width="stroke" />
      <circle v-if="clamped != null" class="ring-value" :cx="size / 2" :cy="size / 2" :r="radius" fill="none" :stroke-width="stroke" stroke-linecap="round" :stroke-dasharray="`${dash} ${perimeter - dash}`" :transform="`rotate(-90 ${size / 2} ${size / 2})`" />
    </svg>
    <span class="ring-number" :style="{ fontSize: Math.max(11, size * 0.32) + 'px' }">{{ pending ? '…' : clamped ?? '—' }}</span>
  </span>
</template>
<style scoped>
.score-ring { position: relative; display: inline-grid; place-items: center; flex-shrink: 0; }
.score-ring > svg, .ring-number { grid-area: 1 / 1; }
.ring-track { stroke: #e8ebf1; }
.ring-number { font-weight: 600; font-variant-numeric: tabular-nums; line-height: 1; color: var(--text-tertiary); z-index: 1; }
.score-ring.high .ring-value { stroke: #1a9e6a; }
.score-ring.high .ring-number { color: #137a52; }
.score-ring.mid .ring-value { stroke: #d9930d; }
.score-ring.mid .ring-number { color: #a96f05; }
.score-ring.low .ring-value { stroke: #98a2b3; }
.score-ring.low .ring-number { color: var(--text-secondary); }
.score-ring.none .ring-number { color: var(--text-tertiary); }
.score-ring.pending .ring-number { color: var(--text-tertiary); }
</style>
