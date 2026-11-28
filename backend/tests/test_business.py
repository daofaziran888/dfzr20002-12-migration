"""会展布展协作平台 - 跨模块业务数据链路测试。

每条测试覆盖至少两个模块的完整数据流，验证真实业务结果。
"""
import sys
import unittest

import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import exhibition, service_for
from app.store import store


class TestVenueToBoothChain(unittest.TestCase):
    """场馆→展位关联链：创建场馆→创建展位→验证关联关系。"""

    def setUp(self):
        self.store = store

    def test_venue_booth_linking_chain(self):
        """展位BOOT-A01应属于A馆主展厅。"""
        result = exhibition.booth_venue_info("BOOT-A01")
        self.assertTrue(result["ok"], f"关联查询应成功: {result.get('reason')}")
        self.assertEqual(result["venue_name"], "A馆主展厅")
        self.assertIsNotNone(result.get("venue"))
        booth = result.get("booth", {})
        self.assertEqual(booth.get("展位编号"), "BOOT-A01")

    def test_venue_capacity_check_with_booths(self):
        """A馆可用面积2000㎡，BOOT-A01(600)+BOOT-A02(400)=1000，未超限。"""
        quota = exhibition.check_venue_capacity(1)
        self.assertTrue(quota["ok"])
        self.assertEqual(quota["quota"]["remaining"], 1000)

    def test_venue_capacity_bounded(self):
        """B馆可用面积800㎡，仅BOOT-B01(300)，剩余500。"""
        quota = exhibition.check_venue_capacity(2)
        self.assertTrue(quota["ok"])
        self.assertEqual(quota["quota"]["remaining"], 500)

    def test_nonexistent_venue_fails(self):
        """不存在的场馆查找应失败。"""
        quota = exhibition.check_venue_capacity(999)
        self.assertFalse(quota["ok"])


class TestDesignToBoothToElectricalChain(unittest.TestCase):
    """设计→展位→用电回路：三级关联链。"""

    def setUp(self):
        self.store = store

    def test_design_links_to_booth(self):
        """设计方案1的备注是'BOOT-A01'，应关联到展位BOOT-A01。"""
        result = exhibition.design_booth_info(1)
        self.assertTrue(result["ok"])
        self.assertTrue(result.get("linked"))
        booth = result.get("booth", {})
        self.assertEqual(booth.get("展位编号"), "BOOT-A01")

    def test_design_load_vs_circuit_power(self):
        """设计方案1用电负荷80kW，回路为75kW(40+35)，未超限。"""
        design = self.store.find("design", 1)
        design_load = float(str(design.get("用电负荷", "0")).replace("kW", ""))
        self.assertEqual(design_load, 80)

        power_result = exhibition.check_electrical_quota("BOOT-A01")
        self.assertTrue(power_result["ok"])
        self.assertLessEqual(power_result["quota"]["total_circuit_power"], design_load)

    def test_design_load_over_by_circuit(self):
        """设计方案2用电负荷50kW，BOOT-A02回路70kW(35+35)，超限。"""
        design = self.store.find("design", 2)
        design_load = float(str(design.get("用电负荷", "0")).replace("kW", ""))
        self.assertEqual(design_load, 50)

        power_result = exhibition.check_electrical_quota("BOOT-A02")
        self.assertFalse(power_result["ok"])
        self.assertIn("超过", power_result.get("reason", ""))


class TestExhibitorToBoothChain(unittest.TestCase):
    """参展商→展位关联链。"""

    def setUp(self):
        self.store = store

    def test_exhibitor_links_to_correct_booth(self):
        """参展商1的备注说明'BOOT-A01'，应关联展位BOOT-A01。"""
        result = exhibition.exhibitor_booth_info(1)
        self.assertTrue(result["ok"])
        self.assertTrue(result.get("linked"))
        booth = result.get("booth", {})
        self.assertEqual(booth.get("展位编号"), "BOOT-A01")
        exhibitor = result.get("exhibitor", {})
        self.assertEqual(exhibitor.get("企业名称"), "星辰科技有限公司")

    def test_exhibitor2_links_to_booth_a02(self):
        """参展商2关联BOOT-A02。"""
        result = exhibition.exhibitor_booth_info(2)
        self.assertTrue(result["ok"])
        self.assertEqual(result.get("booth_no"), "BOOT-A02")


class TestMaterialToDesignToBoothChain(unittest.TestCase):
    """物料→设计→展位三级关联。"""

    def setUp(self):
        self.store = store

    def test_material_links_to_design_and_booth(self):
        """物料1备注BOOT-A01，应关联设计1(备注BOOT-A01)和展位BOOT-A01。"""
        result = exhibition.material_design_info(1)
        self.assertTrue(result["ok"])
        self.assertTrue(result.get("linked"))
        design = result.get("design", {})
        self.assertEqual(design.get("设计风格"), "现代科技风")
        booth = result.get("booth", {})
        self.assertEqual(booth.get("展位编号"), "BOOT-A01")

    def test_material_unlinked_design_returns_none(self):
        """物料不存在的ID应失败。"""
        result = exhibition.material_design_info(999)
        self.assertFalse(result["ok"])


class TestEventToVenueBoothChain(unittest.TestCase):
    """突发事件→场馆/展位关联。"""

    def setUp(self):
        self.store = store

    def test_incident_links_to_booth_location(self):
        """事件1发生位置'BOOT-A01顶部'，应关联展位BOOT-A01。"""
        result = exhibition.incident_venue_info(1)
        self.assertTrue(result["ok"])
        self.assertTrue(result.get("linked"))
        booth = result.get("booth")
        self.assertIsNotNone(booth)
        self.assertEqual(booth.get("展位编号"), "BOOT-A01")


class TestHandoverToScheduleChain(unittest.TestCase):
    """交场→排期关联。"""

    def setUp(self):
        self.store = store

    def test_handover_links_to_active_schedule(self):
        """交场单1应关联到当前已确认的排期计划。"""
        result = exhibition.handover_schedule_info(1)
        self.assertTrue(result["ok"])
        self.assertTrue(result.get("linked"))
        schedule = result.get("schedule")
        self.assertIsNotNone(schedule)
        self.assertEqual(schedule.get("status"), "已确认")
        self.assertEqual(schedule.get("活动名称"), "2026秋季科技文化博览会")


class TestCrossModuleSnapshot(unittest.TestCase):
    """全局跨模块快照：展位全链路。"""

    def setUp(self):
        self.store = store

    def test_cross_snapshot_includes_all_modules(self):
        """BOOT-A01的跨模块快照应包含场馆、参展商、设计、物料等。"""
        result = exhibition.cross_module_snapshot("BOOT-A01")
        self.assertTrue(result["ok"])
        self.assertIsNotNone(result.get("venue"))
        self.assertEqual(len(result.get("exhibitors", [])), 1)
        self.assertEqual(len(result.get("designs", [])), 1)
        self.assertEqual(len(result.get("materials", [])), 2)
        self.assertEqual(len(result.get("electricals", [])), 2)
        self.assertEqual(len(result.get("constructions", [])), 5)
        self.assertEqual(len(result.get("checklists", [])), 4)
        self.assertGreater(result.get("module_count", 0), 5,
                          "BOOT-A01应有超过5个关联模块")

    def test_cross_snapshot_booth_b01(self):
        """BOOT-B01的跨模块快照应包含场馆、参展商、物料等。"""
        result = exhibition.cross_module_snapshot("BOOT-B01")
        self.assertTrue(result["ok"])
        self.assertIsNotNone(result.get("venue"))
        self.assertEqual(result.get("venue").get("场馆名称"), "B馆多功能厅")


class TestCrossModuleServiceValidation(unittest.TestCase):
    """跨模块服务校验：登记/确认时的关联校验。"""

    def setUp(self):
        self.store = store

    def test_electrical_validate_booth_must_exist(self):
        """用电回路登记时所属展位必须存在。"""
        svc = service_for("electrical")
        values = {
            "回路编号": "TEST-001", "额定功率": "30",
            "所属展位": "NONEXISTENT-BOOTH"
        }
        errors = svc.validate_entry(values)
        booth_errors = [e for e in errors if "不存在" in e]
        self.assertGreater(len(booth_errors), 0,
                          "不存在的展位应报错")

    def test_handover_validate_booth_must_exist(self):
        """交场单登记时遗留事项展位必须存在。"""
        svc = service_for("handover")
        values = {
            "交出班组": "测试", "接收人员": "测试",
            "遗留事项": "NONEXISTENT-BOOTH", "交接时刻": "2026-09-20"
        }
        errors = svc.validate_entry(values)
        booth_errors = [e for e in errors if "不存在" in e]
        self.assertGreater(len(booth_errors), 0)

    def test_exhibitor_validate_booth_reference(self):
        """参展商登记时备注说明引用的展位必须存在。"""
        svc = service_for("exhibitor")
        values = {
            "企业名称": "测试公司", "展品类别": "测试",
            "联系人": "测试", "合同金额": "100",
            "备注说明": "BOOT-ZZ99"
        }
        errors = svc.validate_entry(values)
        booth_errors = [e for e in errors if "不存在" in e]
        self.assertGreater(len(booth_errors), 0)


class TestFullDataFlowChain(unittest.TestCase):
    """全链路：场馆→展位→设计→用电→物料→巡检→验收→交场。"""

    def setUp(self):
        self.store = store

    def test_full_chain_booth_a01(self):
        """BOOT-A01完整链路：A馆→BOOT-A01→现代科技风设计→2回路(75kW)→
        2种物料→1家参展商→5进度节点→4验收项→2交场（在途单+已签结旧单）。"""
        snapshot = exhibition.cross_module_snapshot("BOOT-A01")
        self.assertTrue(snapshot["ok"])

        # 验证每一步环节
        self.assertEqual(snapshot["venue"]["场馆名称"], "A馆主展厅")
        self.assertEqual(len(snapshot["exhibitors"]), 1)
        self.assertEqual(snapshot["exhibitors"][0]["企业名称"], "星辰科技有限公司")
        self.assertEqual(len(snapshot["designs"]), 1)
        self.assertEqual(snapshot["designs"][0]["设计风格"], "现代科技风")

        # 材料：2种
        self.assertEqual(len(snapshot["materials"]), 2)
        material_names = [m["物料名称"] for m in snapshot["materials"]]
        self.assertIn("铝合金型材", material_names)
        self.assertIn("钢化玻璃板", material_names)

        # 电气回路：2路，75kW <= 80kW
        self.assertEqual(len(snapshot["electricals"]), 2)
        circuits_total = sum(
            float(str(c.get("额定功率", "0")).replace("kW", ""))
            for c in snapshot["electricals"]
        )
        design_load = float(str(snapshot["designs"][0].get("用电负荷", "0")).replace("kW", ""))
        self.assertLessEqual(circuits_total, design_load,
                            f"回路总功率{circuits_total}kW应≤设计负荷{design_load}kW")

        # 进度节点：5个
        self.assertEqual(len(snapshot["constructions"]), 5)
        self.assertEqual(snapshot["constructions"][0]["节点名称"], "基础结构搭建")

        # 验收清单：4条
        self.assertEqual(len(snapshot["checklists"]), 4)

        # 安全巡检：1条
        self.assertEqual(len(snapshot["safeties"]), 1)
        self.assertEqual(snapshot["safeties"][0]["检查点位"], "BOOT-A01")

        # 交场单：2单（在途 v1.0 单 + 早已签结的旧回执单）
        self.assertEqual(len(snapshot["handovers"]), 2)

        # 事件日志中应至少有变更传播操作
        self.assertGreaterEqual(snapshot["module_count"], 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)