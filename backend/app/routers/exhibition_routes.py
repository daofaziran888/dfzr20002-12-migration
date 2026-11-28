"""跨模块会展引擎路由：执行历史、进度推进、配额视图等集成接口。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services import exhibition

exhibition_router = APIRouter(prefix="/api/exhibition", tags=["跨模块引擎"])


@exhibition_router.get("/{booth_no}/history")
def booth_history(booth_no: str) -> dict:
    """展位执行历史：反查指定展位从规划到交场的全部事件。"""
    result = exhibition.booth_execution_history(booth_no)
    if result.get("booth") is None:
        raise HTTPException(status_code=404, detail=f"展位 {booth_no} 不存在")
    return result


@exhibition_router.post("/{booth_no}/advance")
def advance_construction(booth_no: str) -> dict:
    """推进布展进度节点（需要提供 node_id 参数）。"""
    booth = exhibition.store.find_booth(booth_no)
    if booth is None:
        raise HTTPException(status_code=404, detail=f"展位 {booth_no} 不存在")
    return {"booth": booth, "message": "请调用 POST /api/exhibition/advance/{node_id} 指定进度节点"}


@exhibition_router.post("/advance/{node_id}")
def advance_node(node_id: int) -> dict:
    """推进指定进度节点，含 DAG 拓扑前置校验和环检测。"""
    result = exhibition.topological_advance(node_id)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["reason"])
    return result


@exhibition_router.get("/quota")
def quota_overview() -> dict:
    """面积与功率配额综合结论：场馆容量、用电超载、排期冲突、DAG环检测。"""
    return exhibition.quota_summary()


@exhibition_router.get("/quota/venue/{venue_id}")
def venue_quota(venue_id: int) -> dict:
    """单个场馆的面积配额结论。"""
    result = exhibition.check_venue_capacity(venue_id)
    if not result.get("quota"):
        raise HTTPException(status_code=404, detail=result.get("reason", "场馆不存在"))
    return result


@exhibition_router.get("/quota/booth/{booth_no}")
def booth_power_quota(booth_no: str) -> dict:
    """单个展位的功率配额结论。"""
    result = exhibition.check_electrical_quota(booth_no)
    if not result.get("quota"):
        raise HTTPException(status_code=404, detail=result.get("reason", "展位不存在"))
    return result


@exhibition_router.post("/checklist/{checklist_id}/signoff")
def checklist_signoff(checklist_id: int) -> dict:
    """验收签收：巡检通过才能签收验收项。"""
    validation = exhibition.validate_checklist_signoff(checklist_id)
    if not validation["ok"]:
        raise HTTPException(status_code=400, detail=validation["reason"])

    item = exhibition.store.find("checklist", checklist_id)
    item["status"] = "已确认"
    item["pending"] = False
    return {"ok": True, "reason": "签收完成", "item": item, "validation": validation}


@exhibition_router.post("/handover/{handover_id}/confirm")
def confirm_handover(handover_id: int) -> dict:
    """交场确认：验收清单全部签收才能交场；已办结单重复提交幂等回放，不会重复交场。"""
    result = exhibition.do_handover(handover_id)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["reason"])
    return result


@exhibition_router.get("/handover/{handover_id}/receipt")
def handover_receipt(handover_id: int) -> dict:
    """v2 交场回执：接班人凭原办理编号打开即可回查交场结果或需补签的验收项。

    v1.0 交场记录在首次读取时兼容迁移为 v2 回执，已办结旧单保留当时冻结的已签范围。
    """
    result = exhibition.handover_receipt_view(handover_id)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["reason"])
    return result


@exhibition_router.get("/booth/{booth_no}/handover-receipts")
def booth_handover_receipts(booth_no: str) -> dict:
    """同一展位的全部交场回执（含早已签结的旧交场单），用于接班人回查历史。"""
    result = exhibition.booth_handover_receipts(booth_no)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["reason"])
    return result


@exhibition_router.post("/change/{change_id}/issue")
def issue_change_order(change_id: int) -> dict:
    """签发变更指令：触发进度回退与重新验收传播。"""
    result = exhibition.propagate_change_order(change_id)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["reason"])
    return result


@exhibition_router.get("/conflicts")
def schedule_conflicts() -> dict:
    """运输排期冲突检测。"""
    conflicts = exhibition.detect_schedule_conflicts()
    return {"conflicts": conflicts, "count": len(conflicts)}


@exhibition_router.get("/dag/validate")
def dag_validate() -> dict:
    """DAG拓扑环检测与拓扑排序。"""
    nodes = exhibition.store.rows("construction")
    cycle = exhibition.detect_cycle(nodes)
    order = exhibition.build_dag_order(nodes) if cycle is None else []
    return {
        "cycle": cycle,
        "has_cycle": cycle is not None,
        "topological_order": order,
        "node_count": len(nodes),
    }


@exhibition_router.get("/safety/{booth_no}")
def safety_status(booth_no: str) -> dict:
    """展位安全巡检状态。"""
    return exhibition.check_safety_gate(booth_no)


# ---------- 跨模块关联查询路由 ----------

@exhibition_router.get("/booth/{booth_no}/venue")
def booth_venue(booth_no: str) -> dict:
    """展位→场馆关联查询。"""
    result = exhibition.booth_venue_info(booth_no)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["reason"])
    return result


@exhibition_router.get("/exhibitor/{exhibitor_id}/booth")
def exhibitor_booth(exhibitor_id: int) -> dict:
    """参展商→展位关联查询。"""
    result = exhibition.exhibitor_booth_info(exhibitor_id)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["reason"])
    return result


@exhibition_router.get("/design/{design_id}/booth")
def design_booth(design_id: int) -> dict:
    """设计→展位关联查询。"""
    result = exhibition.design_booth_info(design_id)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["reason"])
    return result


@exhibition_router.get("/material/{material_id}/design")
def material_design(material_id: int) -> dict:
    """物料→设计关联查询。"""
    result = exhibition.material_design_info(material_id)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["reason"])
    return result


@exhibition_router.get("/incident/{incident_id}/venue")
def incident_venue(incident_id: int) -> dict:
    """事件→场馆关联查询。"""
    result = exhibition.incident_venue_info(incident_id)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["reason"])
    return result


@exhibition_router.get("/handover/{handover_id}/schedule")
def handover_schedule(handover_id: int) -> dict:
    """交场→排期关联查询。"""
    result = exhibition.handover_schedule_info(handover_id)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["reason"])
    return result


@exhibition_router.get("/booth/{booth_no}/cross-snapshot")
def cross_snapshot(booth_no: str) -> dict:
    """展位跨模块全局快照。"""
    result = exhibition.cross_module_snapshot(booth_no)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["reason"])
    return result