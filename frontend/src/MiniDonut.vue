<script setup lang="ts">
import { computed } from 'vue'
// 迷你环形图：用于「构成」类指标（如内部/外部人数），只按真实计数分段，不做装饰。
// 半径取 15.9155，使圆周长恰好为 100，可直接用百分比作为 dash 长度。
interface Segment { label: string; value: number; color: string }
const props = withDefaults(defineProps<{ segments: Segment[]; size?: number; thickness?: number }>(), { size: 40, thickness: 7 })
const total = computed(() => props.segments.reduce((sum, s) => sum + Math.max(0, s.value), 0))
const arcs = computed(() => {
  let acc = 0
  return props.segments.map(s => {
    const pct = total.value > 0 ? (Math.max(0, s.value) / total.value) * 100 : 0
    const arc = { ...s, pct, offset: acc }
    acc += pct
    return arc
  })
})
const label = computed(() => props.segments.map(s => `${s.label} ${s.value}`).join('，') || '暂无数据')
</script>
<template>
  <svg class="mini-donut" :width="size" :height="size" viewBox="0 0 42 42" role="img" :aria-label="label">
    <title>{{ label }}</title>
    <circle cx="21" cy="21" r="15.9155" :stroke-width="thickness" fill="none" stroke="#eceff6" />
    <circle
      v-for="a in arcs" :key="a.label"
      cx="21" cy="21" r="15.9155" fill="none"
      :stroke="a.color" :stroke-width="thickness"
      :stroke-dasharray="`${a.pct} ${100 - a.pct}`"
      :stroke-dashoffset="-a.offset"
      transform="rotate(-90 21 21)"
    />
  </svg>
</template>
<style scoped>
.mini-donut { flex-shrink: 0; display: block; }
</style>
