from __future__ import annotations
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from apps.ev import services

ev_bp = Blueprint("ev", __name__)


@ev_bp.route("/")
def home():
    return redirect(url_for("ev.list_partners"))


@ev_bp.route("/partners", methods=["GET"])
def list_partners():
    partners = services.svc_list_partners()
    return render_template("partners.html", partners=partners)


@ev_bp.route("/partners", methods=["POST"])
def create_partner():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Partner name is required", "error")
    else:
        services.svc_create_partner(name); flash("Partner created", "success")
    return redirect(url_for("ev.list_partners"))


@ev_bp.route("/partners/<int:partner_id>", methods=["GET"])
def partner_detail(partner_id: int):
    partner = services.svc_get_partner(partner_id)
    if not partner:
        flash("Partner not found", "error")
        return redirect(url_for("ev.list_partners"))
    vehicles = services.svc_list_partner_vehicles(partner.id)
    return render_template("partner_detail.html", partner=partner, vehicles=vehicles)


@ev_bp.route("/partners/<int:partner_id>/vehicles", methods=["POST"])
def add_vehicle(partner_id: int):
    partner = services.svc_get_partner(partner_id)
    if not partner:
        flash("Partner not found", "error")
        return redirect(url_for("ev.list_partners"))
    vin = (request.form.get("vin") or "").strip()
    make = (request.form.get("make") or "").strip() or None
    model = (request.form.get("model") or "").strip() or None
    year  = request.form.get("year")
    year_i = int(year) if year and year.isdigit() else None
    if not vin:
        flash("VIN is required", "error")
    else:
        services.svc_create_vehicle(partner.id, vin, make, model, year_i); flash("Vehicle added", "success")
    return redirect(url_for("ev.partner_detail", partner_id=partner.id))


@ev_bp.route("/vehicles/<int:vehicle_id>", methods=["GET"])
def vehicle_detail(vehicle_id: int):
    vehicle = services.svc_get_vehicle(vehicle_id)
    if not vehicle:
        flash("Vehicle not found", "error")
        return redirect(url_for("ev.list_partners"))
    reports = services.svc_list_vehicle_reports(vehicle.id)
    reports_parsed = [
        {"report": r, "parsed": (json.loads(r.result_json or "{}") if r.result_json else {})}
        for r in reports
    ]
    return render_template("vehicle_detail.html", vehicle=vehicle, reports=reports_parsed)


@ev_bp.route("/vehicles/<int:vehicle_id>/reports", methods=["POST"])
def add_report(vehicle_id: int):
    vehicle = services.svc_get_vehicle(vehicle_id)
    if not vehicle:
        flash("Vehicle not found", "error")
        return redirect(url_for("ev.list_partners"))
    json_text = (request.form.get("json_text") or "").strip()
    upload = request.files.get("json_file")
    payload_str = ""
    if upload and upload.filename:
        payload_str = upload.read().decode("utf-8", errors="replace")
    elif json_text:
        payload_str = json_text
    if not payload_str:
        flash("Please provide a JSON file or paste JSON", "error")
        return redirect(url_for("ev.vehicle_detail", vehicle_id=vehicle.id))
    try:
        raw_obj = json.loads(payload_str)
    except Exception as e:
        flash(f"Invalid JSON: {e}", "error")
        return redirect(url_for("ev.vehicle_detail", vehicle_id=vehicle.id))
    services.svc_create_report(vehicle.id, raw_obj)
    flash("Report created", "success")
    return redirect(url_for("ev.vehicle_detail", vehicle_id=vehicle.id))


@ev_bp.route("/reports/<int:report_id>/download", methods=["GET"])
def download_report_html(report_id: int):
    html = services.svc_render_report_html(report_id)
    return Response(html, mimetype="text/html",
                    headers={"Content-Disposition": f"attachment; filename=report_{report_id}.html"})
