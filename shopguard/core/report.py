"""Builds a self-contained HTML report (images embedded, no internet needed to view it).

The report opens in any browser, and the browser's Print → Save as PDF gives a PDF copy.
"""

from __future__ import annotations

import base64
from html import escape
from pathlib import Path

from shopguard.config import APP_NAME, APP_VERSION
from shopguard.core.analyzer import AnalysisResult
from shopguard.core.incidents import STATUS_CONFIRMED, STATUS_FALSE_ALARM, Incident, Sample
from shopguard.core.video import format_duration, format_file_size, format_timestamp

SEVERITY_COLORS = {"High": "#e5484d", "Medium": "#f5a524", "Low": "#8b93a7"}
CHART_WIDTH, CHART_HEIGHT = 900, 160
MAX_CHART_POINTS = 600

CSS = """
body { font-family: "Segoe UI", Arial, sans-serif; color: #1c2230; margin: 0; background: #f4f6fa; }
.page { max-width: 960px; margin: 0 auto; padding: 32px; }
header { display: flex; justify-content: space-between; align-items: flex-end;
         border-bottom: 3px solid #4c8dff; padding-bottom: 12px; margin-bottom: 24px; }
h1 { margin: 0; font-size: 26px; } h2 { font-size: 18px; margin: 28px 0 12px; }
.muted { color: #6b7385; font-size: 13px; }
.cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.card { background: #fff; border: 1px solid #e3e7ef; border-radius: 10px; padding: 14px 16px; }
.card .value { font-size: 22px; font-weight: 600; margin-top: 4px; }
table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; }
th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid #eef1f6; font-size: 13px; }
th { background: #f0f3f9; color: #4a5263; font-weight: 600; }
.incident { background: #fff; border: 1px solid #e3e7ef; border-radius: 10px; padding: 16px;
            margin-bottom: 14px; display: grid; grid-template-columns: 320px 1fr; gap: 16px;
            page-break-inside: avoid; }
.incident img { width: 100%; border-radius: 6px; }
.badge { display: inline-block; padding: 2px 10px; border-radius: 99px; color: #fff;
         font-size: 12px; font-weight: 600; }
.dismissed { opacity: 0.55; }
.notice { background: #fff7e6; border: 1px solid #f5d38a; border-radius: 10px; padding: 12px 16px;
          font-size: 13px; margin-top: 24px; }
svg { background: #fff; border: 1px solid #e3e7ef; border-radius: 10px; }
"""


def build_html_report(result: AnalysisResult, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_render(result), encoding="utf-8")
    return output_path


def _render(result: AnalysisResult) -> str:
    video = result.video
    active = result.active_incidents
    confirmed = sum(i.status == STATUS_CONFIRMED for i in result.incidents)
    dismissed = sum(i.status == STATUS_FALSE_ALARM for i in result.incidents)
    highest = max((i.peak_confidence for i in active), default=0.0)

    summary_rows = "".join(
        f"<tr><td>#{i.id}</td><td>{format_timestamp(i.start)} – {format_timestamp(i.end)}</td>"
        f"<td>{format_duration(i.duration)}</td><td>{_badge(i)}</td>"
        f"<td>{i.peak_confidence:.0%}</td><td>{escape(i.status)}</td></tr>"
        for i in result.incidents
    ) or '<tr><td colspan="6">No suspicious activity was detected.</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{APP_NAME} report – {escape(video.name)}</title><style>{CSS}</style></head>
<body><div class="page">
<header>
  <div><h1>Shoplifting analysis report</h1>
  <div class="muted">{escape(video.name)}</div></div>
  <div class="muted">Generated {result.created_at:%d %b %Y, %H:%M}<br>{APP_NAME} {APP_VERSION}</div>
</header>

<div class="cards">
  <div class="card"><div class="muted">Suspected incidents</div><div class="value">{len(active)}</div></div>
  <div class="card"><div class="muted">Confirmed by reviewer</div><div class="value">{confirmed}</div></div>
  <div class="card"><div class="muted">Dismissed as false alarm</div><div class="value">{dismissed}</div></div>
  <div class="card"><div class="muted">Highest confidence</div><div class="value">{highest:.0%}</div></div>
</div>

<h2>Video and analysis details</h2>
<table>
  <tr><th>File</th><td>{escape(str(video.path))}</td><th>Length</th><td>{format_duration(video.duration)}</td></tr>
  <tr><th>Resolution</th><td>{video.resolution}</td><th>Frame rate</th><td>{video.fps:.1f} fps</td></tr>
  <tr><th>File size</th><td>{format_file_size(video.file_size)}</td><th>Frames analysed</th><td>{result.frames_analyzed:,}</td></tr>
  <tr><th>Sensitivity</th><td>{escape(result.sensitivity)} (threshold {result.threshold:.0%})</td>
      <th>Analysis time</th><td>{format_duration(result.processing_time)}</td></tr>
  <tr><th>Model</th><td>{escape(result.model_name)}</td><th>Sampling</th><td>{result.sample_fps:g} frames per second</td></tr>
</table>

<h2>Suspicion score over time</h2>
{_chart(result.samples, result.incidents, result.threshold, video.duration)}

<h2>Incident summary</h2>
<table><tr><th>#</th><th>Time</th><th>Length</th><th>Severity</th><th>Peak confidence</th><th>Review status</th></tr>
{summary_rows}</table>

{"<h2>Incident details</h2>" if result.incidents else ""}
{"".join(_incident_section(i) for i in result.incidents)}

<div class="notice"><b>Important:</b> these are <b>suspected</b> incidents found automatically and may
include false alarms. Always watch the footage yourself before taking any action, and handle any
suspect through your security staff and the police, never by force.</div>
</div></body></html>"""


def _badge(incident: Incident) -> str:
    color = SEVERITY_COLORS[incident.severity]
    return f'<span class="badge" style="background:{color}">{incident.severity}</span>'


def _incident_section(incident: Incident) -> str:
    image = ""
    if incident.snapshot_path and Path(incident.snapshot_path).is_file():
        data = base64.b64encode(Path(incident.snapshot_path).read_bytes()).decode("ascii")
        image = f'<img src="data:image/jpeg;base64,{data}" alt="Incident {incident.id} snapshot">'
    css_class = "incident dismissed" if incident.status == STATUS_FALSE_ALARM else "incident"
    return f"""<div class="{css_class}"><div>{image}</div><div>
<h3 style="margin:0 0 6px">Incident #{incident.id} · {escape(incident.label)} {_badge(incident)}</h3>
<p>{escape(incident.description)}</p>
<table>
  <tr><th>Start</th><td>{format_timestamp(incident.start)}</td><th>End</th><td>{format_timestamp(incident.end)}</td></tr>
  <tr><th>Peak confidence</th><td>{incident.peak_confidence:.0%}</td><th>Average confidence</th><td>{incident.mean_confidence:.0%}</td></tr>
  <tr><th>Review status</th><td colspan="3">{escape(incident.status)}</td></tr>
</table></div></div>"""


def _chart(samples: list[Sample], incidents: list[Incident], threshold: float, duration: float) -> str:
    """Inline SVG line chart of the suspicion score, with incidents shaded."""
    if not samples or duration <= 0:
        return '<p class="muted">No data.</p>'
    step = max(1, len(samples) // MAX_CHART_POINTS)
    points = []
    for i in range(0, len(samples), step):
        chunk = samples[i:i + step]
        top = max(chunk, key=lambda s: s.score)  # keep peaks visible when downsampling
        points.append((top.time, top.score))

    def x(t: float) -> float:
        return t / duration * CHART_WIDTH

    def y(score: float) -> float:
        return CHART_HEIGHT - 10 - score * (CHART_HEIGHT - 20)

    shaded = "".join(
        f'<rect x="{x(i.start):.1f}" y="0" width="{max(2.0, x(i.end) - x(i.start)):.1f}" '
        f'height="{CHART_HEIGHT}" fill="{SEVERITY_COLORS[i.severity]}" opacity="0.15"/>'
        for i in incidents
    )
    line = " ".join(f"{x(t):.1f},{y(s):.1f}" for t, s in points)
    return f"""<svg viewBox="0 0 {CHART_WIDTH} {CHART_HEIGHT}" width="100%">
{shaded}
<line x1="0" x2="{CHART_WIDTH}" y1="{y(threshold):.1f}" y2="{y(threshold):.1f}"
      stroke="#e5484d" stroke-dasharray="6 4" stroke-width="1"/>
<polyline points="{line}" fill="none" stroke="#4c8dff" stroke-width="1.5"/>
<text x="6" y="{y(threshold) - 4:.1f}" font-size="11" fill="#e5484d">threshold {threshold:.0%}</text>
</svg>
<div class="muted">0:00 to {format_timestamp(duration)}. Shaded areas are incidents.</div>"""
