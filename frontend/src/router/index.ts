import { createRouter, createWebHistory } from 'vue-router'

import Overview from '@/views/Overview.vue'
import WorkbenchView from '@/views/WorkbenchView.vue'
import BoothPipelineView from '@/views/BoothPipelineView.vue'
import QuotaDashboardView from '@/views/QuotaDashboardView.vue'
import HandoverReceiptView from '@/views/HandoverReceiptView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'overview', component: Overview },
    { path: '/pipeline', name: 'pipeline', component: BoothPipelineView },
    { path: '/dashboard', name: 'dashboard', component: QuotaDashboardView },
    { path: '/handover-receipts', name: 'handover-receipts', component: HandoverReceiptView },
    { path: '/:moduleKey', name: 'module', component: WorkbenchView, props: true },
  ],
})

export default router