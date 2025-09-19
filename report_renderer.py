from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape

def render_report(
    data: Dict[str, Any],
    out_html_path: str,
    template_dir: Optional[str] = None,
    template_name: str = "report.html",
) -> Dict[str, str]:
    """
    Render an HTML report from the analysis dict and write it to out_html_path.
    Returns: {'html': <absolute path>}
    """
    out: Dict[str, str] = {}
    out_html = Path(out_html_path)
    tmpl_dir = Path(template_dir) if template_dir else out_html.parent

    env = Environment(
        loader=FileSystemLoader(str(tmpl_dir)),
        autoescape=select_autoescape()
    )
    tmpl = env.get_template(template_name)

    v = data.get("vehicle_info", {})
    html = tmpl.render(
        v=v,
        soh=data.get("soh"),
        cdc=data.get("cdc_data", {}),
        anomalies=data.get("anomalies", {"voltage": {}, "temperature": {}}),
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        year=datetime.utcnow().year,
    )

    out_html.write_text(html, encoding="utf-8")
    out["html"] = str(out_html.resolve())
    return out
