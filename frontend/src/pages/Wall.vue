<template>
  <div class="wall">
    <h1 class="serif">愿望墙</h1>
    <p class="tag">无顶栏 · 瀑布流 · 点卡片看详情</p>
    <div class="claim-bar">
      <input v-model="name" placeholder="认领用的名字" />
      <span class="tag">墙卡可直接认领</span>
    </div>
    <p v-if="err" class="err">{{ err }}</p>
    <div class="masonry">
      <article v-for="w in rows" :key="w.id" class="card" @click="$router.push('/wishes/'+w.id)">
        <h3>{{ w.title || '（无标题）' }}</h3>
        <p>{{ w.note }}</p>
        <div class="card-foot">
          <span class="badge" :class="badgeClass(w)">{{ badgeText(w) }}</span>
          <button v-if="canClaim(w)" class="ghost small" @click.stop="claim(w)">认领</button>
        </div>
      </article>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
const rows = ref([])
const name = ref('访客')
const err = ref('')

function canClaim(w) { return w.status === 'open' || w.status === 'released' }
function badgeClass(w) {
  if (w.status === 'claimed') return w.sweep_eligible ? 'stale' : 'claimed'
  return 'open'
}
function badgeText(w) {
  if (w.status === 'claimed') return w.sweep_eligible ? '超时待扫尾' : '已认领 · ' + (w.claimer || '—')
  return '可认领'
}

async function load() { rows.value = await api('/wishes') }
async function claim(w) {
  err.value = ''
  try {
    await api('/wishes/' + w.id + '/claim', { method: 'POST', body: JSON.stringify({ claimer: name.value }) })
    await load()
  } catch (e) { err.value = e.message }
}
onMounted(load)
</script>
