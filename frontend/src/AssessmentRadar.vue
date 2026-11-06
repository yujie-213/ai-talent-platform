<script setup lang="ts">
import { computed } from 'vue'
const props=defineProps<{dimensions:Record<string,{score:number;maximum:number}>}>()
// 同一份固定试卷内按满分归一化；不跨试卷推定维度可比性。
const measured=computed(()=>Object.entries(props.dimensions).filter(([,d])=>d.maximum>0))
function point(index:number,ratio:number){const angle=2*Math.PI*index/measured.value.length-Math.PI/2;return [160+Math.cos(angle)*100*ratio,145+Math.sin(angle)*100*ratio]}
const outline=computed(()=>measured.value.map((_,i)=>point(i,1).join(',')).join(' '))
const scores=computed(()=>measured.value.map(([,d],i)=>point(i,d.score/d.maximum).join(',')).join(' '))
</script>
<template><figure v-if="measured.length>=3"><svg viewBox="0 0 320 300" role="img" aria-label="本次试卷实际测量维度得分比例雷达图" style="width:100%;max-width:400px"><polygon :points="outline" fill="none" stroke="#a2b8b1"/><line v-for="(_,i) in measured" :key="i" x1="160" y1="145" :x2="point(i,1)[0]" :y2="point(i,1)[1]" stroke="#dae3df"/><polygon :points="scores" fill="#278c7044" stroke="#278c70" stroke-width="2"/><text v-for="([name],i) in measured" :key="name" :x="point(i,1.18)[0]" :y="point(i,1.18)[1]" text-anchor="middle" font-size="11">{{name}}</text></svg><figcaption class="muted">本次试卷各维度得分 / 满分。只比较本试卷测得表现，不表示总体能力。</figcaption></figure><p v-else class="muted">实际测得维度少于三个，使用分项条形图；其余能力为未测评。</p></template>
