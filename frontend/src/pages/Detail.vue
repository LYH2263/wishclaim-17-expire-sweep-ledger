<template>
  <div class="wall">
    <h1 class="serif">{{ w.title }}</h1>
    <p>{{ w.note }}</p>
    <p class="tag">状态 {{ w.status }} · 认领人 {{ w.claimer || '—' }}</p>
    <p v-if="err" class="err">{{ err }}</p>
    <input v-model="claimer" placeholder="你的名字" />
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button @click="claim">认领锁定</button>
      <button class="ghost" @click="release">释放</button>
      <button class="ghost" @click="fulfill">核销完成</button>
    </div>
    <h2 class="serif" style="margin-top:24px">事件</h2>
    <p v-if="!events.length" class="tag">暂无释放事件</p>
    <article v-for="e in events" :key="e.id" class="card event-card">
      <strong>{{ e.source === 'reclaim' ? '抢占释放' : '扫尾释放' }}</strong>
      <span class="tag">原认领人 {{ e.claimer || '—' }} · {{ e.at }}</span>
      <router-link class="tag batch-link" :title="e.batch_id" to="/ledger">批次 {{ e.batch_id.slice(0, 13) }}…</router-link>
    </article>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
const props = defineProps({ id: String })
const w = ref({})
const events = ref([])
const claimer = ref('访客')
const err = ref('')
async function load() {
  const [wish, ev] = await Promise.all([
    api('/wishes/' + props.id),
    api('/wishes/' + props.id + '/events'),
  ])
  w.value = wish
  events.value = ev.events
}
async function act(path) {
  err.value = ''
  try { await api(path, { method: 'POST', body: '{}' }); await load() } catch (e) { err.value = e.message }
}
function claim() {
  err.value = ''
  api('/wishes/' + props.id + '/claim', { method: 'POST', body: JSON.stringify({ claimer: claimer.value }) })
    .then(load).catch(e => { err.value = e.message })
}
function release() { act('/wishes/' + props.id + '/release') }
function fulfill() { act('/wishes/' + props.id + '/fulfill') }
onMounted(load)
</script>
