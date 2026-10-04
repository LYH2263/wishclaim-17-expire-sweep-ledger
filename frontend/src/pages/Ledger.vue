<template>
  <div class="wall">
    <h1 class="serif">扫尾台账</h1>
    <p class="tag">干跑只预览不改动；提交才释放过期锁并记账</p>
    <div class="sweep-bar">
      <button class="ghost" :disabled="busy" @click="preview">干跑预览</button>
      <button :disabled="busy" @click="commit">提交扫尾</button>
    </div>
    <p v-if="msg" class="tag">{{ msg }}</p>
    <p v-if="err" class="err">{{ err }}</p>

    <section v-if="previewRows.length">
      <h2 class="serif">干跑候选（{{ previewRows.length }}）</h2>
      <table class="ledger-table">
        <thead><tr><th>wish_id</th><th>claimer</th><th>claimed_at</th><th>expires_at</th></tr></thead>
        <tbody>
          <tr v-for="r in previewRows" :key="r.wish_id">
            <td><router-link :to="'/wishes/' + r.wish_id">#{{ r.wish_id }}</router-link></td>
            <td>{{ r.claimer || '—' }}</td>
            <td>{{ r.claimed_at }}</td>
            <td>{{ r.expires_at }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <h2 class="serif" style="margin-top:24px">释放批次</h2>
    <p v-if="!batches.length" class="tag">暂无台账记录</p>
    <article v-for="b in batches" :key="b.batch_id" class="card">
      <div class="batch-head">
        <strong :title="b.batch_id">{{ b.batch_id }}</strong>
        <span class="tag">{{ b.source === 'reclaim' ? '抢占释放' : '扫尾提交' }} · {{ b.created_at }}</span>
        <span class="tag">候选 {{ b.candidate_count }} · 释放 {{ b.released_count }} · 跳过 {{ b.skipped_count }}</span>
      </div>
      <table class="ledger-table">
        <thead><tr><th>wish_id</th><th>标题</th><th>原 claimer</th><th>claimed_at</th><th>released_at</th></tr></thead>
        <tbody>
          <tr v-for="e in b.entries" :key="b.batch_id + '-' + e.wish_id">
            <td><router-link :to="'/wishes/' + e.wish_id">#{{ e.wish_id }}</router-link></td>
            <td>{{ e.title || '（已删除）' }}</td>
            <td>{{ e.claimer || '—' }}</td>
            <td>{{ e.claimed_at }}</td>
            <td>{{ e.released_at }}</td>
          </tr>
        </tbody>
      </table>
    </article>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
const batches = ref([])
const previewRows = ref([])
const busy = ref(false)
const err = ref('')
const msg = ref('')

async function loadLedger() { batches.value = (await api('/ledger')).batches }
async function preview() {
  err.value = ''; msg.value = ''
  try {
    const res = await api('/sweep/dry-run', { method: 'POST', body: '{}' })
    previewRows.value = res.candidates
    msg.value = '干跑时刻 ' + res.checked_at + ' · 候选 ' + res.count + ' 行（未改动任何数据）'
  } catch (e) { err.value = e.message }
}
async function commit() {
  err.value = ''; msg.value = ''; busy.value = true
  try {
    const res = await api('/sweep/commit', { method: 'POST', body: '{}' })
    previewRows.value = []
    if (res.batch_id) {
      msg.value = '已提交批次 ' + res.batch_id + ' · 释放 ' + res.released_count + ' 行'
    } else {
      msg.value = '没有需要释放的过期锁，未建批次'
    }
    await loadLedger()
  } catch (e) { err.value = e.message } finally { busy.value = false }
}
onMounted(loadLedger)
</script>
