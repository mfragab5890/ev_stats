from __future__ import annotations
from typing import Optional
from apps.ev.models import db, Partner, Vehicle, VehicleReport


def create_partner(name: str) -> Partner:
    p = Partner(name=name)
    db.session.add(p)
    db.session.commit()
    return p


def list_partners() -> list[Partner]:
    return Partner.query.order_by(Partner.created_at.desc()).all()


def get_partner(pid: int) -> Optional[Partner]:
    return Partner.query.get(pid)


def create_vehicle(partner_id: int, vin: str, make: str | None, model: str | None, year: int | None) -> Vehicle:
    v = Vehicle(partner_id=partner_id, vin=vin, make=make, model=model, year=year)
    db.session.add(v)
    db.session.commit()
    return v


def list_partner_vehicles(partner_id: int) -> list[Vehicle]:
    return Vehicle.query.filter_by(partner_id=partner_id).order_by(Vehicle.created_at.desc()).all()


def get_vehicle(vid: int) -> Optional[Vehicle]:
    return Vehicle.query.get(vid)


def create_report(vehicle_id: int, raw_json: str, result_json: str) -> VehicleReport:
    r = VehicleReport(vehicle_id=vehicle_id, raw_log_json=raw_json, result_json=result_json)
    db.session.add(r)
    db.session.commit()
    return r


def list_vehicle_reports(vehicle_id: int) -> list[VehicleReport]:
    return VehicleReport.query.filter_by(vehicle_id=vehicle_id).order_by(VehicleReport.created_at.desc()).all()


def get_report(rid: int) -> Optional[VehicleReport]:
    return VehicleReport.query.get(rid)
