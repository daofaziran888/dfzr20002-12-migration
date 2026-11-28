"""交场确认 v2 迁移与回执测试。

覆盖新版本上线时的交场迁移场景：
1. v1.0 在途交场单兼容迁移为可回查的 v2 回执，带入展位归属与已签验收范围；
2. 已办结旧回执保留确认当时冻结的已签范围，切换格式不重算；
3. 重复提交/重复确认不会多做一次交场（幂等）；
4. 未办结单仍须通过所属展位验收，新增待签造成新旧范围冲突时可被查回；
5. 接班人凭原办理编号能查到在途单与另一份早已签结的交场单。
"""
import sys
import copy
import unittest

import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import exhibition, service_for
from app.store import store
from app.seed import SEED_ROWS


def _seed_handover(handover_id: int) -> dict:
    return copy.deepcopy(next(r for r in SEED_ROWS["handover"] if r["id"] == handover_id))


def _restore_handover(handover_id: int) -> dict:
    handover = store.find("handover", handover_id)
    handover.clear()
    handover.update(_seed_handover(handover_id))
    return handover


def _handover_events(entry_id: int, action: str | None = None) -> list:
    events = store.event_log.for_module("handover", entry_id)
    if action:
        events = [e for e in events if e["action"] == action]
    return events


class TestV1Migration(unittest.TestCase):
    """v1.0 交场记录兼容迁移为 v2 回执。"""

    def setUp(self):
        self.handover_id = 1  # HAND-0001：送出确认后未收到回执的 v1.0 在途单
        self._saved_handover = _seed_handover(self.handover_id)

    def tearDown(self):
        _restore_handover(self.handover_id)

    def _reset_to_v1(self) -> dict:
        return _restore_handover(self.handover_id)

    def test_pending_v1_record_migrates_to_v2_receipt(self):
        handover = self._reset_to_v1()
        self.assertEqual(handover["回执版本"], "v1.0")
        self.assertNotIn("交场回执", handover)

        result = exhibition.handover_receipt_view(self.handover_id)
        self.assertTrue(result["ok"], result.get("reason"))
        self.assertEqual(result["receipt_version"], "v2.0")
        self.assertEqual(result["migrated_from"], "v1.0")
        self.assertFalse(result["frozen"])
        # 原办理编号不变，工作台仍可凭编号打开
        self.assertEqual(result["registration_no"], "HAND-0001")
        # 展位归属被带入回执
        self.assertEqual(result["booth_no"], "BOOT-A01")
        self.assertEqual(result["venue_name"], "A馆主展厅")
        self.assertEqual(result["booth_owner"], "张策展")

    def test_migration_is_idempotent_and_logged_once(self):
        # 先归一到已迁移状态，再验证后续重复读取不会重复迁移
        exhibition.handover_receipt_view(self.handover_id)
        before = len(_handover_events(self.handover_id, "迁移v2回执"))
        exhibition.handover_receipt_view(self.handover_id)
        exhibition.migrate_handover_receipt(self.handover_id)
        after = len(_handover_events(self.handover_id, "迁移v2回执"))
        self.assertEqual(after, before, "已迁移记录重复读取不再产生迁移事件")

    def test_migrated_pending_receipt_reflects_live_signed_scope(self):
        self._reset_to_v1()
        # 种子数据：A01 验收项 1/2/3 已签，4 待签
        result = exhibition.handover_receipt_view(self.handover_id)
        self.assertEqual(result["signed_count"], 3)
        self.assertEqual(result["unsigned_count"], 1)
        unsigned_ids = [item["id"] for item in result["unsigned_scope"]]
        self.assertIn(4, unsigned_ids)
        signed_ids = {item["id"] for item in result["signed_scope"]}
        self.assertEqual(signed_ids, {1, 2, 3})


class TestFrozenCompletedReceipt(unittest.TestCase):
    """已办结旧回执保留当时已签范围，格式切换不重算。"""

    def setUp(self):
        self.handover_id = 3  # HAND-0003：早已签结的 v1.0 交场单

    def test_completed_v1_receipt_keeps_frozen_scope_after_migration(self):
        result = exhibition.handover_receipt_view(self.handover_id)
        self.assertTrue(result["ok"])
        self.assertEqual(result["receipt_version"], "v2.0")
        self.assertTrue(result["frozen"])
        # 冻结的是确认当时的 3 条已签范围
        self.assertEqual(result["signed_count"], 3)
        self.assertEqual([item["id"] for item in result["signed_scope"]], [1, 2, 3])
        self.assertEqual(result["unsigned_count"], 0)

    def test_frozen_receipt_not_recomputed_when_scope_conflicts_appear(self):
        # 当前 A01 实际已有 4 条验收项（第 4 条待签），冻结回执不得被改写为 4 条
        current_ids = [item["id"] for item in store.booth_checklist("BOOT-A01")]
        self.assertIn(4, current_ids)
        result = exhibition.handover_receipt_view(self.handover_id)
        self.assertEqual(result["signed_count"], 3)
        self.assertEqual(result["scope_conflicts"], [])
        handover = store.find("handover", self.handover_id)
        self.assertEqual(handover["交场回执"]["checklist_total_at_confirm"], 3)


class TestIdempotentConfirmation(unittest.TestCase):
    """重复提交不能多做一次交场。"""

    def setUp(self):
        self.handover_id = 3  # 已签结旧单

    def test_confirm_twice_does_not_repeat_handover(self):
        before_events = len(_handover_events(self.handover_id, "完成交场"))
        first = exhibition.do_handover(self.handover_id)
        second = exhibition.do_handover(self.handover_id)
        after_events = len(_handover_events(self.handover_id, "完成交场"))

        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertTrue(second.get("idempotent"), "第二次确认应命中幂等回放")
        self.assertEqual(after_events, before_events, "重复确认不得新增交场事件")
        self.assertEqual(store.find("handover", self.handover_id)["status"], "已确认")

    def test_generic_action_endpoint_shares_idempotent_gate(self):
        svc = service_for("handover")
        before_events = len(_handover_events(self.handover_id, "完成交场"))
        entry, message = svc.run_action(self.handover_id, "完成交场")
        after_events = len(_handover_events(self.handover_id, "完成交场"))
        self.assertIsNotNone(entry)
        self.assertIn("重复提交", message)
        self.assertEqual(after_events, before_events)


class TestPendingHandoverGateAndConflict(unittest.TestCase):
    """未办结单仍须通过所属展位验收，新增待签产生范围冲突。"""

    def setUp(self):
        self.handover_id = 1  # HAND-0001 在途单
        self.created_checklist_id: int | None = None
        self._saved_handover = _seed_handover(self.handover_id)

    def tearDown(self):
        # 恢复在途交场单与验收项 4 的初始状态，移除运行时新增验收项，保证套件可重复执行
        _restore_handover(self.handover_id)
        item4 = store.find("checklist", 4)
        if item4 is not None:
            item4["status"] = "待确认"
            item4["pending"] = True
        if self.created_checklist_id is not None:
            rows = store.rows("checklist")
            store.rows("checklist")[:] = [
                r for r in rows if int(r.get("id", 0)) != self.created_checklist_id
            ]
            store.rebuild_indices()

    def test_pending_handover_blocked_by_unsigned_booth_checklist(self):
        result = exhibition.do_handover(self.handover_id)
        self.assertFalse(result["ok"])
        unsigned = result.get("unsigned_items", [])
        self.assertEqual([item["id"] for item in unsigned], [4])

    def test_new_pending_item_creates_scope_conflict_on_pending_receipt(self):
        # 验收员为 A01 新增一项待签，新旧记录验收范围发生冲突
        new_item = {
            "id": store.next_id("checklist"), "status": "待确认", "pending": True,
            "abnormal": False, "验收条目": "新增应急照明核验", "验收标准": "断电后自动点亮",
            "负责班组": "BOOT-A01", "完成时间": "2026-09-19",
            "登记编号": "CHEC-NEW", "负责人": "郑安全", "生效版本": "v2.0",
            "备注说明": "新版本上线后新增待签",
        }
        store.rows("checklist").append(new_item)
        store.rebuild_indices()
        self.created_checklist_id = int(new_item["id"])

        result = exhibition.handover_receipt_view(self.handover_id)
        self.assertTrue(result["ok"])
        conflict_ids = {c["id"] for c in result["scope_conflicts"]}
        self.assertIn(new_item["id"], conflict_ids)
        self.assertIn(4, conflict_ids, "原待签项 4 也应出现在需补签范围中")
        self.assertEqual(result["unsigned_count"], 2)

        # 同展位已签结旧回执不受新增待签影响
        frozen = exhibition.handover_receipt_view(3)
        self.assertTrue(frozen["frozen"])
        self.assertEqual(frozen["signed_count"], 3)
        self.assertEqual(frozen["scope_conflicts"], [])

    def test_complete_after_signing_freezes_v2_receipt_once(self):
        item4 = store.find("checklist", 4)
        item4["status"] = "已确认"
        item4["pending"] = False

        result = exhibition.do_handover(self.handover_id)
        self.assertTrue(result["ok"], result.get("reason"))
        self.assertFalse(result.get("idempotent"))
        receipt = result["receipt"]
        self.assertTrue(receipt["frozen"])
        self.assertEqual(receipt["receipt_version"], "v2.0")
        self.assertEqual(receipt["signed_count"], 4)
        self.assertEqual(receipt["unsigned_count"], 0)

        handover = store.find("handover", self.handover_id)
        self.assertEqual(handover["回执版本"], "v2.0")
        self.assertEqual(handover["交场回执"]["checklist_total_at_confirm"], 4)

        # 再次确认即为幂等回放，不再产生第二次交场
        repeat = exhibition.do_handover(self.handover_id)
        self.assertTrue(repeat["ok"])
        self.assertTrue(repeat["idempotent"])
        confirm_events = _handover_events(self.handover_id, "完成交场")
        self.assertEqual(len(confirm_events), 1)


class TestBoothReceiptLookup(unittest.TestCase):
    """接班人凭展位/办理编号回查全部交场回执。"""

    def test_booth_receipts_include_pending_and_completed(self):
        result = exhibition.booth_handover_receipts("BOOT-A01")
        self.assertTrue(result["ok"])
        receipts = result["receipts"]
        registrations = {r["registration_no"] for r in receipts}
        self.assertIn("HAND-0001", registrations, "应能查回在途原请求")
        self.assertIn("HAND-0003", registrations, "应能查回早已签结的另一份交场单")
        statuses = {r["registration_no"]: r["status"] for r in receipts}
        self.assertEqual(statuses["HAND-0001"], "待确认")
        self.assertEqual(statuses["HAND-0003"], "已确认")

    def test_unknown_booth_rejected(self):
        result = exhibition.booth_handover_receipts("BOOT-ZZ99")
        self.assertFalse(result["ok"])

    def test_unknown_handover_rejected(self):
        result = exhibition.handover_receipt_view(9999)
        self.assertFalse(result["ok"])


class TestNewHandoverDefaultsV2(unittest.TestCase):
    """新版本登记的交场单默认 v2.0 回执格式。"""

    def setUp(self):
        self.created_id: int | None = None

    def tearDown(self):
        if self.created_id is not None:
            rows = store.rows("handover")
            store.rows("handover")[:] = [
                r for r in rows if int(r.get("id", 0)) != self.created_id
            ]
            store.rebuild_indices()

    def test_create_entry_stamps_v2_receipt_version(self):
        svc = service_for("handover")
        values = {
            "交出班组": "测试班组", "接收人员": "接班人",
            "遗留事项": "BOOT-B01", "交接时刻": "2026-09-20 09:00",
        }
        entry, errors = svc.create_entry(values)
        self.assertEqual(errors, [])
        self.assertIsNotNone(entry)
        self.created_id = int(entry["id"])
        self.assertEqual(entry["回执版本"], "v2.0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
