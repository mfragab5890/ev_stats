from __future__ import annotations
from datetime import datetime
from pathlib import Path
import json, re
from typing import Dict, Any, Optional

from report_renderer import render_report

# Defaults (can be overridden when calling build_reports)
DEFAULT_OUT_DIR = Path.cwd() / "report_outputs"
DEFAULT_TEMPLATE_DIR = Path.cwd() / "templates"
TEMPLATE_NAME = "report.html"

def _save_report_json(data: Dict[str, Any], out_dir: Path) -> tuple[Path, str, str]:
    """
    Write the analysis result to ./report_outputs/<VIN>_<UTCtimestamp>.json
    Returns: (json_path, vin_safe, ts)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    vin = (data.get("vehicle_info", {}) or {}).get("vin", "unknown")
    vin_safe = re.sub(r"[^A-Za-z0-9_.-]", "-", str(vin)) or "unknown"
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"{vin_safe}_{ts}.json"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return json_path, vin_safe, ts

def build_reports(
    data: Dict[str, Any],
    *,
    template_dir: Path = DEFAULT_TEMPLATE_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> Dict[str, Optional[str]]:
    """
    Generate two artifacts ONLY:
      - JSON: ./report_outputs/<VIN>_<UTC>.json
      - HTML: ./report_outputs/<VIN>_<UTC>.html
    """
    if not template_dir.is_dir():
        raise FileNotFoundError(f"Template dir not found: {template_dir} (expecting {TEMPLATE_NAME} inside)")

    # 1) JSON
    json_path, vin_safe, ts = _save_report_json(data, out_dir)

    # 2) HTML (no PDF generation)
    html_out = out_dir / f"{vin_safe}_{ts}.html"
    paths = render_report(
        data,
        out_html_path=str(html_out),
        template_dir=str(template_dir),
        template_name=TEMPLATE_NAME,
    )

    info = {
        "json": str(json_path),
        "html": paths.get("html"),
    }
    print(f"Building report: {json.dumps(info, indent=4)}")
    return info

# Optional CLI for manual testing
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python build_report.py <path-to-output.json> [template_dir] [out_dir]")
        raise SystemExit(1)

    in_json = Path(sys.argv[1])
    tdir = Path(sys.argv[2]) if len(sys.argv) >= 3 else DEFAULT_TEMPLATE_DIR
    odir = Path(sys.argv[3]) if len(sys.argv) >= 4 else DEFAULT_OUT_DIR

    data = json.loads(in_json.read_text(encoding="utf-8"))
    out = build_reports(data, template_dir=tdir, out_dir=odir)
    print(json.dumps(out, indent=2))
