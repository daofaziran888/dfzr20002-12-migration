/** 会展引擎专用类型 */

export interface EventRecord {
  id: number
  timestamp: number
  module: string
  entry_id: number
  action: string
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  extra: Record<string, unknown>
}

export interface SafetyStatus {
  ok: boolean
  reason: string
  total_inspections: number
  failed_inspections: Record<string, unknown>[]
}

export interface ElectricalQuota {
  booth_no: string
  design_load: number
  total_circuit_power: number
  over_draw: number
  circuits: Record<string, unknown>[]
}

export interface ExhibitionHistory {
  booth_no: string
  booth: Record<string, unknown> | null
  design: Record<string, unknown> | null
  events: EventRecord[]
  event_count: number
  current_safety: SafetyStatus
  current_electrical: { ok: boolean; reason: string; quota: ElectricalQuota }
  schedule_conflicts: Record<string, unknown>[]
}

export interface QuotaItem {
  venue: string
  venue_id: number
  ok: boolean
  reason: string
  quota: Record<string, unknown>
}

export interface PowerQuotaItem {
  ok: boolean
  reason: string
  quota: ElectricalQuota
}

export interface ScheduleConflict {
  transport_id: number
  exhibit: string
  arrival: string
  schedule_id: number
  event: string
  setup_start: string
  conflict: string
}

export interface QuotaSummary {
  area_quotas: QuotaItem[]
  power_quotas: PowerQuotaItem[]
  schedule_conflicts: ScheduleConflict[]
  schedule_conflict_count: number
  dag_cycle: string[] | null
  dag_ok: boolean
  overall_ok: boolean
}

export interface DAGStatus {
  cycle: string[] | null
  has_cycle: boolean
  topological_order: string[]
  node_count: number
}

export interface HandoverResult {
  ok: boolean
  reason: string
  handover?: Record<string, unknown>
  validation?: Record<string, unknown>
  idempotent?: boolean
  receipt?: HandoverReceipt
}

export interface HandoverScopeItem {
  id: number
  item: string
  status: string
}

export interface HandoverScopeConflict {
  id: number
  item: string
  type: string
  current_status: string
}

export interface HandoverReceipt {
  ok: boolean
  handover_id: number
  registration_no: string
  booth_no: string
  status: string
  receipt_version: string
  frozen: boolean
  migrated_from: string | null
  booth_owner: string
  venue_name: string
  signed_scope: HandoverScopeItem[]
  unsigned_scope: HandoverScopeItem[]
  scope_conflicts: HandoverScopeConflict[]
  signed_count: number
  unsigned_count: number
  checklist_total?: number
  checklist_total_at_confirm?: number
  confirmed_at: string
}

export interface BoothHandoverReceipts {
  ok: boolean
  booth_no: string
  count: number
  receipts: HandoverReceipt[]
}