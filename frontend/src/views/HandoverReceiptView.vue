<template>
  <section class="page handover-receipt-page">
    <header class="page-head">
      <div>
        <h2>交场回执（v2）</h2>
        <p class="page-desc">
          接班人凭原办理编号打开 v1.0 交场请求，自动迁移为可回查的 v2 回执；已签结旧单保留当时冻结的已签范围。
        </p>
      </div>
    </header>

    <form class="filter-bar" @submit.prevent="loadById">
      <label class="filter-item">
        <span>交场单办理编号（数字 ID）</span>
        <input v-model="handoverIdInput" placeholder="如 1（HAND-0001）" data-testid="receipt-id-input" />
      </label>
      <button class="btn primary" data-testid="receipt-query" type="submit">打开原请求</button>
      <label class="filter-item">
        <span>按展位回查全部交场单</span>
        <input v-model="boothNoInput" placeholder="如 BOOT-A01" data-testid="receipt-booth-input" />
      </label>
      <button class="btn" data-testid="receipt-booth-query" type="button" @click="loadByBooth">查展位回执</button>
    </form>

    <p v-if="errorMessage" class="error-text" data-testid="receipt-error">{{ errorMessage }}</p>

    <!-- 同展位全部回执（含早已签结的另一份交场单） -->
    <section v-if="boothReceipts.length" class="info-card">
      <h4>展位 {{ boothNoInput }} 的全部交场回执（{{ boothReceipts.length }}）</h4>
      <table class="data-table">
        <thead>
          <tr>
            <th>办理编号</th>
            <th>展位</th>
            <th>当前状态</th>
            <th>回执版本</th>
            <th>已签/待签</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in boothReceipts" :key="item.handover_id">
            <td>{{ item.registration_no }}</td>
            <td>{{ item.booth_no }}</td>
            <td>{{ item.status }}</td>
            <td>{{ item.receipt_version }}<template v-if="item.migrated_from">（{{ item.migrated_from }} 迁移）</template></td>
            <td>{{ item.signed_count }} / {{ item.unsigned_count }}</td>
            <td>
              <button class="link" type="button" @click="openReceipt(item.handover_id)">查看回执</button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- v2 交场回执详情 -->
    <article v-if="receipt" class="receipt-card" data-testid="receipt-detail">
      <header class="receipt-head">
        <div>
          <h3>{{ receipt.registration_no }} · {{ receipt.booth_no }}</h3>
          <p class="page-desc">
            回执版本 {{ receipt.receipt_version }}
            <template v-if="receipt.migrated_from">（由 {{ receipt.migrated_from }} 兼容迁移）</template>
            ｜ 当前状态：<strong :class="receipt.frozen ? 'text-success' : 'text-warn'">{{ receipt.status }}</strong>
            <template v-if="receipt.frozen"> ｜ 已冻结，保留确认当时的已签范围</template>
          </p>
        </div>
        <button
          v-if="!receipt.frozen"
          class="btn primary"
          data-testid="receipt-confirm"
          type="button"
          :disabled="confirming"
          @click="confirm"
        >
          {{ confirming ? '提交中…' : '重新提交交场确认' }}
        </button>
      </header>

      <section class="info-card">
        <h4>展位归属</h4>
        <dl class="receipt-grid">
          <div><dt>展位编号</dt><dd>{{ receipt.booth_no }}</dd></div>
          <div><dt>所属场馆</dt><dd>{{ receipt.venue_name || '—' }}</dd></div>
          <div><dt>展位负责人</dt><dd>{{ receipt.booth_owner || '—' }}</dd></div>
          <div><dt>办理编号</dt><dd>{{ receipt.registration_no }}</dd></div>
          <div v-if="receipt.confirmed_at"><dt>确认时刻</dt><dd>{{ receipt.confirmed_at }}</dd></div>
        </dl>
      </section>

      <section class="info-card">
        <h4>已签验收范围（{{ receipt.signed_count }}）</h4>
        <ul v-if="receipt.signed_scope.length" class="scope-list signed">
          <li v-for="item in receipt.signed_scope" :key="item.id">
            <span class="scope-id">#{{ item.id }}</span>{{ item.item }}
            <em>{{ item.status }}</em>
          </li>
        </ul>
        <p v-else class="empty-state">暂无已签验收项</p>
      </section>

      <section class="info-card">
        <h4>需补签验收项（{{ receipt.unsigned_count }}）</h4>
        <ul v-if="receipt.unsigned_scope.length" class="scope-list unsigned">
          <li v-for="item in receipt.unsigned_scope" :key="item.id">
            <span class="scope-id">#{{ item.id }}</span>{{ item.item }}
            <em>{{ item.status }}</em>
          </li>
        </ul>
        <p v-else class="empty-state">验收范围已全部签收</p>
      </section>

      <section v-if="!receipt.frozen && receipt.scope_conflicts.length" class="info-card conflict-card">
        <h4>新旧记录验收范围冲突（{{ receipt.scope_conflicts.length }}）</h4>
        <ul class="scope-list conflict">
          <li v-for="conflict in receipt.scope_conflicts" :key="conflict.id">
            <span class="scope-id">#{{ conflict.id }}</span>{{ conflict.item }}
            <em>{{ conflict.type }} · 当前 {{ conflict.current_status }}</em>
          </li>
        </ul>
      </section>

      <p v-if="confirmMessage" class="confirm-message" :class="confirmOk ? 'text-success' : 'error-text'">
        {{ confirmMessage }}
      </p>
    </article>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  confirmHandover,
  fetchBoothHandoverReceipts,
  fetchHandoverReceipt,
} from '@/api/exhibition-client'
import type { HandoverReceipt } from '@/data/exhibition-types'

const route = useRoute()
const router = useRouter()

const handoverIdInput = ref(String(route.query.id ?? '1'))
const boothNoInput = ref(String(route.query.booth ?? 'BOOT-A01'))
const receipt = ref<HandoverReceipt | null>(null)
const boothReceipts = ref<HandoverReceipt[]>([])
const errorMessage = ref('')
const confirming = ref(false)
const confirmMessage = ref('')
const confirmOk = ref(false)

async function loadById() {
  errorMessage.value = ''
  confirmMessage.value = ''
  const id = Number(handoverIdInput.value)
  if (!Number.isInteger(id) || id <= 0) {
    errorMessage.value = '请输入有效的交场单办理编号'
    return
  }
  try {
    receipt.value = await fetchHandoverReceipt(id)
    router.replace({ query: { ...route.query, id } })
  } catch (error) {
    receipt.value = null
    errorMessage.value = error instanceof Error ? error.message : '交场回执查询失败'
  }
}

async function loadByBooth() {
  errorMessage.value = ''
  try {
    const result = await fetchBoothHandoverReceipts(boothNoInput.value.trim())
    boothReceipts.value = result.receipts
    router.replace({ query: { ...route.query, booth: boothNoInput.value.trim() } })
  } catch (error) {
    boothReceipts.value = []
    errorMessage.value = error instanceof Error ? error.message : '展位交场回执查询失败'
  }
}

function openReceipt(id: number) {
  handoverIdInput.value = String(id)
  void loadById()
}

async function confirm() {
  if (!receipt.value) return
  confirming.value = true
  confirmMessage.value = ''
  try {
    const result = await confirmHandover(receipt.value.handover_id)
    confirmOk.value = true
    confirmMessage.value = result.idempotent
      ? '该交场单已办结，重复提交未再次交场，已回传既有回执'
      : result.reason
    receipt.value = await fetchHandoverReceipt(receipt.value.handover_id)
    if (boothNoInput.value) await loadByBooth()
  } catch (error) {
    confirmOk.value = false
    confirmMessage.value = error instanceof Error ? error.message : '交场确认失败'
  } finally {
    confirming.value = false
  }
}

void loadById()
void loadByBooth()
</script>

<style scoped>
.receipt-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
  margin-top: 16px;
}
.receipt-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}
.receipt-head h3 { margin: 0 0 4px; }
.receipt-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 8px;
  margin: 0;
}
.receipt-grid dt { font-size: 12px; color: var(--muted); }
.receipt-grid dd { margin: 2px 0 0; font-size: 14px; }
.scope-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.scope-list li {
  display: flex; align-items: center; gap: 8px;
  background: #f8f9fa; border-radius: 6px; padding: 6px 10px; font-size: 13px;
}
.scope-list li em { margin-left: auto; font-style: normal; color: var(--muted); font-size: 12px; }
.scope-id { color: var(--brand); font-weight: 600; }
.scope-list.unsigned li { background: #fff7ed; }
.scope-list.conflict li { background: #fef2f2; }
.conflict-card { border: 1px solid #fecaca; }
.text-success { color: #16a34a; }
.text-warn { color: #d97706; }
.confirm-message { margin-top: 12px; font-size: 13px; }
</style>
