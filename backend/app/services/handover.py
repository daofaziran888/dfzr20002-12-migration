"""交场确认领域服务：验收清单全面签收后才能交场，可反查执行历史。

v2 版本要点：
- 新登记交场单默认使用 v2.0 回执格式；
- v1.0 旧记录在打开/提交时懒迁移为可回查的 v2 回执，带入展位归属与已签范围；
- 已办结旧回执保留确认当时冻结的已签范围，格式切换不重算、不重复交场；
- 完成交场走统一的幂等入口，重复提交不会多做一次交场。
"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.store import store
from app.services import exhibition


class HandoverService(BaseModuleService):
    MODULE = "handover"
    ENTITY = "交场单"
    OPERATION_TERM = "完成交场"
    LIST_FIELDS = ["交出班组", "接收人员", "遗留事项", "交接时刻", "登记编号", "负责人", "生效版本", "备注说明"]
    REQUIRED_FIELDS = ["交出班组", "接收人员", "遗留事项", "交接时刻"]
    STATUS_ORDER = ["草稿", "待确认", "已确认", "已撤回"]
    ACTION_RULES = {"完成交场": "已确认", "提交确认": "待确认", "撤回记录": "已撤回"}
    NEGATIVE_ACTIONS = []
    RELATED_MODULES = ["checklist", "safety", "construction"]

    def validate_entry(self, values: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        booth_no = str(values.get("遗留事项", "")).strip()
        if booth_no:
            booth = store.find_booth(booth_no)
            if booth is None:
                errors.append(f"展位 {booth_no} 不存在，请先登记展位")
        return errors

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        entry, errors = super().create_entry(values)
        if entry is not None:
            # 新版本上线后登记的交场单直接采用 v2.0 回执格式。
            entry["回执版本"] = exhibition.HANDOVER_SCHEMA_V2
        return entry, errors

    def validate_action(self, entry_id: int, action: str) -> tuple[bool, str]:
        if action == "完成交场":
            validation = exhibition.validate_handover(entry_id)
            if not validation["ok"]:
                return False, validation["reason"]
        return True, ""

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(self.MODULE, entry_id)
        if entry is None:
            return None, f"{self.ENTITY} {entry_id} 不存在或已归档"

        if action == "完成交场":
            # 与 /api/exhibition/handover/{id}/confirm 共用幂等门禁与回执冻结逻辑。
            result = exhibition.do_handover(entry_id)
            if not result["ok"]:
                return None, result["reason"]
            return result["handover"], result["reason"]

        if action == "提交确认":
            # v1.0 在途单一经接班人接手即迁移为 v2 回执，已办结单不受影响。
            exhibition.migrate_handover_receipt(entry_id)

        return super().run_action(entry_id, action)

    def get_receipt(self, entry_id: int) -> dict[str, Any] | None:
        result = exhibition.handover_receipt_view(entry_id)
        return result if result.get("ok") else None

    def domain_snapshot(self) -> dict[str, Any]:
        base = super().domain_snapshot()
        rows = store.rows(self.MODULE)
        confirmed = sum(1 for r in rows if r.get("status") == "已确认")
        v2_receipts = sum(
            1 for r in rows
            if (r.get("交场回执") or {}).get("schema_version") == exhibition.HANDOVER_SCHEMA_V2
        )
        base["completed_handovers"] = confirmed
        base["v2_receipts"] = v2_receipts
        return base
