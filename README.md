# EV Battery Health — SoH & Anomaly Report

A compact analysis toolkit and Flask app that parses EV diagnostic logs and produces a clear **Battery Health report**.

Outputs: **JSON** (machine-readable) and **HTML** (human-readable).  
Live (Render): https://ev-batterystatistics.onrender.com
note service might take some time to spin up as it's currently on a free tier if you faced any problem please run the app locally

---

## 1) Overview

- Ingests a JSON log of EV events (`drive`, `charge`, `rest`) that include SoC, energy-in, pack current, cell voltages, and cell temperatures.
- Estimates **State of Health (SoH %)** from charge segments (ΔSoC vs energy added).
- Computes **Equivalent Full Cycles (EFC)** from summed absolute SoC changes.
- Detects **voltage** and **temperature** anomalies (range violations and excessive cell-to-cell spread).
- Writes artifacts to `./report_outputs/`: `<VIN>_<UTC>.json` and `<VIN>_<UTC>.html`.

---

## 2) Assumptions in `soh_analysis.py`

These are pragmatic defaults; you can tune them per pack/OEM.

### 2.1 SoH (charge-segment method)
- A **charge block** is defined as contiguous samples where `event == "charge"`.
- Ignore tiny top-ups: `MIN_DELTA_SOC = 5.0` percentage points.
- For each valid block:  
  `estimated_capacity_kwh = energy_in_kwh_total / (ΔSoC / 100)`  
  `SoH% = (estimated_capacity_kwh / design_capacity_kwh) * 100`
- Samples after reaching **100% SoC** in the same block are ignored to avoid tail effects.
- Final SoH is the **average** over all valid charge blocks in the dataset.

> Rationale: Given typical telemetry (SoC + energy-in), this is the simplest robust estimator. Coulomb counting with high-fidelity current integration and IR tracking is out of scope here, but thresholds are centralized for later refinement.

### 2.2 Cycle counting (EFC)
- We track SoC across the timeline and sum absolute changes:  
  `overall_cycles = Σ|ΔSoC| / 100`.
- We also track **charge-only** SoC changes to report `charge_cycles` and derive `discharge_cycles` = `overall - charge`.

### 2.3 Voltage anomalies
- Per sample, across cell voltages:
  - **Out-of-range**: `MAX_CELL_VOLTAGE = 4.2 V`, `MIN_CELL_VOLTAGE = 2.5 V`.
  - **Imbalance** (max−min across cells) depends on load:
    - At rest: `IMBALANCE_MV_AT_REST = 30 mV`
    - Under load: `IMBALANCE_MV_UNDER_LOAD = 60 mV`
  - Load split via **C-rate** from pack current: `C_RATE_LOAD_THRESHOLD = 0.1 C`.

### 2.4 Temperature anomalies
- Per sample, across cell temps:
  - **Out-of-range**: `MAX_CELL_TEMP_C = 55 °C`, `MIN_CELL_TEMP_C = 0 °C`.
  - **Cell spread**: `MAX_CELLS_TEMP_DIFFERENCE = 5 °C`.

All thresholds live near the top of `soh_analysis.py` for quick tuning.

---

## 3) Input and Output

### 3.1 Expected input (minimal)

```json
{
  "vehicle": {
    "vin": "5YJ3E1EA7KF317000",
    "make": "Tesla",
    "model": "Model 3 LR",
    "year": 2022,
    "design_capacity_kwh": 82.0,
    "nominal_pack_voltage": 360.0
  },
  "logs": [
    {
      "ts": "2025-09-12T07:30:00Z",
      "event": "charge | drive | rest",
      "soc": 72.4,
      "energy_in_kwh": 0.33,
      "pack_current": 12.2,
      "cell_voltages": [ ... ],
      "cell_temps_c":  [ ... ]
    }
  ]
}
```

### 3.2 Analysis output

```json
{
  "vehicle_info": { "...": "..." },
  "soh": 95.69,
  "cdc_data": {
    "overall_cycles": 1.86,
    "charge_cycles": 1.02,
    "discharge_cycles": 0.84
  },
  "anomalies": {
    "voltage": {
      "voltage_range_anomalies": [ ... ],
      "voltage_difference_anomalies": [ ... ]
    },
    "temperature": {
      "temperature_range_anomalies": [ ... ],
      "temperature_difference_anomalies": [ ... ]
    }
  }
}
```

---

## 4) Using the analysis module by itself

### 4.1 CLI

```bash
python soh_analysis.py <path-to-log.json>
```

- Prints the analysis JSON and performance stats (time, memory).
- Returns the same dict from `handle_battery_data_extraction(log_data)`.

### 4.2 From Python

```python
from pathlib import Path
import json
from soh_analysis import handle_battery_data_extraction

data = json.loads(Path("input_log.json").read_text(encoding="utf-8"))
report = handle_battery_data_extraction(data)
print(report)
```

---

## 5) Building artifacts (JSON + HTML)

After running the analysis:

```python
from build_report import build_reports

paths = build_reports(battery_data)
# -> {
#   "json": "./report_outputs/<VIN>_<UTC>.json",
#   "html": "./report_outputs/<VIN>_<UTC>.html"
# }
```

- The HTML is rendered from `templates/report.html` (print-friendly, grid on screen).  
- PDF generation is intentionally omitted in this build; use headless Chromium later for full CSS Grid support if needed.

---

## 6) Flask app

### 6.1 What it does
- Partners → Vehicles → Reports (simple CRUD).
- Upload or paste a log JSON; the server runs the analysis, stores raw result JSON, and writes HTML/JSON artifacts.
- Lists reports with **SoH**, **EFC**, and a combined **anomaly count** per report.
- “Download HTML” link for the static artifact.

### 6.2 Run locally

```bash
python -m venv venv
# Windows PowerShell
venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Migrations (Flask-Migrate or Alembic—use the one you wired)
# If Flask-Migrate:
$env:FLASK_APP = "app:app"
flask db upgrade  # (or: flask db init && flask db migrate && flask db upgrade)

# Start
flask run  # http://127.0.0.1:5010
```

**Config**
- `SQLALCHEMY_DATABASE_URI` defaults to a local SQLite file (see `app.py`).  
- Set `SECRET_KEY` in env for production.

### 6.3 Deploy (Render)
- Build: `pip install -r requirements.txt`
- Start: `alembic upgrade head && gunicorn app:app` (or your chosen WSGI/ASGI runner)
- Env vars: `SECRET_KEY`, `SQLALCHEMY_DATABASE_URI` (Render Postgres recommended)
- Apply migrations on deploy (`flask db upgrade` or `alembic upgrade head`).

---

## 7) Troubleshooting

- **PDF doesn’t match HTML**
  Skipped by design. For future PDF export, use **headless Chromium** (Playwright) for full CSS Grid support.

- **Duplicate vehicles per partner**  
  Ensure a composite unique index `(partner_id, vin)` exists in the model/migration.

---

## 8) Next steps / nice-to-haves
- Confidence interval / quality flag on SoH per charge block (ΔSoC size, temperature window).
- Basic trend lines across multiple reports (SoH vs date, IR proxy vs date).
- Optional DCFC/AC labeling to filter blocks automatically.
- JSON API for CI/testing (e.g., `POST /api/vehicles/<id>/reports`).

---

**Note:** thresholds are intentionally conservative and centralized to make tuning easy. The current estimator is optimized for practicality and speed (single pass).
