from typing import Dict, Any
def render_report_html(result: Dict[str, Any], vehicle: Dict[str, Any], partner: Dict[str, Any]) -> str:
    soh = result.get("soh_percentage"); cycles = result.get("count_of_charge_discharge_cycles")
    anomalies = result.get("anomalies", {}); vimb = anomalies.get("voltage_imbalance", []); over = anomalies.get("overheat", [])
    vh = vehicle or {}; ph = partner or {}
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>Battery Report</title>
<style>body{{font-family:Arial;margin:24px}}.card{{border:1px solid #ddd;padding:16px;border-radius:10px;margin:12px 0}}table{{width:100%;border-collapse:collapse}}th,td{{border-bottom:1px solid #eee;padding:8px}}</style>
</head><body>
<h1>Battery Report</h1>
<div>Partner: {ph.get('name','-')} | Vehicle: {vh.get('vin','-')} {vh.get('make','')} {vh.get('model','')} {vh.get('year','')}</div>
<div class="card"><strong>SoH:</strong> {soh if soh is not None else '-'} % &nbsp; | &nbsp; <strong>Cycles (EFC):</strong> {cycles}</div>
<div class="card"><h3>Anomalies</h3><p>Voltage Imbalance: {len(vimb)} | Overheat: {len(over)}</p>
<table><thead><tr><th>Type</th><th>Timestamp</th><th>Info</th></tr></thead><tbody>
{''.join(f"<tr><td>Voltage</td><td>{a.get('timestamp','')}</td><td>ΔV={a.get('delta_v_mv','?')} mV; C={a.get('c_rate','?')}</td></tr>" for a in vimb)}
{''.join(f"<tr><td>Overheat</td><td>{a.get('timestamp','')}</td><td>Tmax={a.get('t_max_c','?')}°C; Tmin={a.get('t_min_c','?')}°C</td></tr>" for a in over)}
</tbody></table></div></body></html>'''
