/** 跨模块会展引擎 API：执行历史、配额视图、进度推进等。 */
import { request } from './client'
import type {
  ExhibitionHistory,
  QuotaSummary,
  DAGStatus,
  HandoverResult,
  HandoverReceipt,
  BoothHandoverReceipts,
} from '@/data/exhibition-types'

const EXHIBITION_BASE = '/api/exhibition'

export async function fetchBoothHistory(boothNo: string): Promise<ExhibitionHistory> {
  const response = await request(`${EXHIBITION_BASE}/${boothNo}/history`)
  if (!response.ok) throw new Error('执行历史查询失败')
  return await response.json()
}

export async function advanceConstructionNode(nodeId: number): Promise<{ ok: boolean; reason: string }> {
  const response = await request(`${EXHIBITION_BASE}/advance/${nodeId}`, { method: 'POST' })
  return await response.json()
}

export async function fetchQuotaSummary(): Promise<QuotaSummary> {
  const response = await request(`${EXHIBITION_BASE}/quota`)
  if (!response.ok) throw new Error('配额数据读取失败')
  return await response.json()
}

export async function signoffChecklist(checklistId: number): Promise<{ ok: boolean; reason: string }> {
  const response = await request(`${EXHIBITION_BASE}/checklist/${checklistId}/signoff`, { method: 'POST' })
  return await response.json()
}

export async function confirmHandover(handoverId: number): Promise<HandoverResult> {
  const response = await request(`${EXHIBITION_BASE}/handover/${handoverId}/confirm`, { method: 'POST' })
  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))) as { detail?: string }
    throw new Error(detail.detail ?? '交场确认失败')
  }
  return await response.json()
}

export async function fetchHandoverReceipt(handoverId: number): Promise<HandoverReceipt> {
  const response = await request(`${EXHIBITION_BASE}/handover/${handoverId}/receipt`)
  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))) as { detail?: string }
    throw new Error(detail.detail ?? '交场回执查询失败')
  }
  return await response.json()
}

export async function fetchBoothHandoverReceipts(boothNo: string): Promise<BoothHandoverReceipts> {
  const response = await request(`${EXHIBITION_BASE}/booth/${encodeURIComponent(boothNo)}/handover-receipts`)
  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))) as { detail?: string }
    throw new Error(detail.detail ?? '展位交场回执查询失败')
  }
  return await response.json()
}

export async function issueChangeOrder(changeId: number): Promise<{ ok: boolean; reason: string }> {
  const response = await request(`${EXHIBITION_BASE}/change/${changeId}/issue`, { method: 'POST' })
  return await response.json()
}

export async function fetchSafetyStatus(boothNo: string): Promise<{ ok: boolean; reason: string }> {
  const response = await request(`${EXHIBITION_BASE}/safety/${boothNo}`)
  return await response.json()
}

export async function fetchDAGStatus(): Promise<DAGStatus> {
  const response = await request(`${EXHIBITION_BASE}/dag/validate`)
  return await response.json()
}

export async function fetchScheduleConflicts(): Promise<{ conflicts: Record<string, unknown>[]; count: number }> {
  const response = await request(`${EXHIBITION_BASE}/conflicts`)
  return await response.json()
}