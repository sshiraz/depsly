from datetime import datetime, timezone

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="DepSly", description="npm dependency risk analyzer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


def fetch_npm_data(package: str) -> dict:
    resp = requests.get(f"https://registry.npmjs.org/{package}", timeout=10)
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Package '{package}' not found")
    resp.raise_for_status()
    return resp.json()


def fetch_weekly_downloads(package: str) -> int:
    try:
        resp = requests.get(
            f"https://api.npmjs.org/downloads/point/last-week/{package}", timeout=10
        )
        resp.raise_for_status()
        return resp.json().get("downloads", 0)
    except Exception:
        return 0


def calc_blast_radius_score(downloads: int) -> float:
    """Higher downloads = higher blast radius risk (0-100)."""
    if downloads >= 10_000_000:
        return 100
    if downloads >= 1_000_000:
        return 80
    if downloads >= 100_000:
        return 60
    if downloads >= 10_000:
        return 40
    if downloads >= 1_000:
        return 20
    return 10


def calc_maintainer_score(count: int) -> float:
    """Fewer maintainers = higher risk (0-100)."""
    if count <= 1:
        return 100
    if count == 2:
        return 60
    if count <= 4:
        return 30
    return 10


def calc_activity_score(years_since_update: float) -> float:
    """More stale = higher risk (0-100)."""
    if years_since_update >= 3:
        return 100
    if years_since_update >= 2:
        return 80
    if years_since_update >= 1:
        return 60
    if years_since_update >= 0.5:
        return 30
    return 10


def calc_risk_score(blast: float, maintainer: float, activity: float) -> float:
    cve_placeholder = 0
    score = (
        blast * 0.35
        + maintainer * 0.25
        + activity * 0.20
        + cve_placeholder * 0.10
    )
    return round(min(score, 100), 1)


def determine_action(score: float, maintainer_count: int, years_since_update: float) -> str:
    if maintainer_count <= 1 and years_since_update > 2:
        return "REPLACE"
    if score >= 80:
        return "REPLACE"
    if score >= 60:
        return "REVIEW"
    if score >= 40:
        return "MONITOR"
    return "ACCEPT"


@app.get("/analyze/{package:path}")
def analyze(package: str):
    data = fetch_npm_data(package)

    latest_version = data.get("dist-tags", {}).get("latest", "unknown")
    maintainers = data.get("maintainers", [])
    maintainers_count = len(maintainers)

    time_info = data.get("time", {})
    last_modified = time_info.get("modified", "")
    if last_modified:
        modified_dt = datetime.fromisoformat(last_modified.replace("Z", "+00:00"))
        years_since_update = round(
            (datetime.now(timezone.utc) - modified_dt).days / 365.25, 2
        )
    else:
        years_since_update = 99.0

    downloads = fetch_weekly_downloads(package)

    blast = calc_blast_radius_score(downloads)
    maintainer = calc_maintainer_score(maintainers_count)
    activity = calc_activity_score(years_since_update)
    risk_score = calc_risk_score(blast, maintainer, activity)
    action = determine_action(risk_score, maintainers_count, years_since_update)

    factors = {
        "blast_radius": {"score": blast, "weight": "35%", "detail": f"{downloads:,} weekly downloads"},
        "maintainer_risk": {"score": maintainer, "weight": "25%", "detail": f"{maintainers_count} maintainer(s)"},
        "activity_risk": {"score": activity, "weight": "20%", "detail": f"{years_since_update} years since update"},
        "cve_risk": {"score": 0, "weight": "10%", "detail": "placeholder"},
    }

    summary = f"{package}@{latest_version} — risk {risk_score}/100 — action: {action}"

    return {
        "package": package,
        "latest_version": latest_version,
        "downloads_weekly": downloads,
        "maintainers_count": maintainers_count,
        "last_updated": last_modified,
        "years_since_update": years_since_update,
        "risk_score": risk_score,
        "action": action,
        "factors": factors,
        "summary": summary,
        "suggested_alternatives": [],
    }
