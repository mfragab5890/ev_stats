from __future__ import annotations
import json
from typing import Optional, Dict, Any
from apps.ev import db_utils
from build_report import build_reports
from soh_analysis import handle_battery_data_extraction


def svc_create_partner(name: str):
    return db_utils.create_partner(name)


def svc_list_partners():
    return db_utils.list_partners()


def svc_get_partner(pid: int):
    return db_utils.get_partner(pid)


def svc_create_vehicle(partner_id: int, vin: str, make: Optional[str], model: Optional[str], year: Optional[int]):
    return db_utils.create_vehicle(partner_id, vin, make, model, year)


def svc_list_partner_vehicles(partner_id: int):
    return db_utils.list_partner_vehicles(partner_id)


def svc_get_vehicle(vid: int):
    return db_utils.get_vehicle(vid)


def svc_create_report(vehicle_id: int, raw_obj: Dict[str, Any]) -> int:
    result = handle_battery_data_extraction(raw_obj)
    rid = db_utils.create_report(vehicle_id, json.dumps(raw_obj, ensure_ascii=False), json.dumps(result, ensure_ascii=False)).id
    return rid


def svc_list_vehicle_reports(vehicle_id: int):
    return db_utils.list_vehicle_reports(vehicle_id)


def svc_get_report(rid: int):
    return db_utils.get_report(rid)


def svc_render_report_html(rid: int) -> str:
    rep = db_utils.get_report(rid)
    if not rep: return "<h1>Report not found</h1>"
    result = json.loads(rep.result_json)
    reports = build_reports(result, get_html=True)
    return reports["html"]
