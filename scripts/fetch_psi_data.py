"""Fetch NASA PSI combustion investigations, metadata, and experimental CSV tables into data/raw/psi/.

Run:
    .venv/bin/python -m scripts.fetch_psi_data
"""
import json
from pathlib import Path

from backend.app.core.config import settings
from backend.app.core.http import get_session

PSI_BASE = "https://psi.nasa.gov/geode-py/ws"
RAW_PSI_DIR = settings.DATA_RAW_DIR / "psi"


def download_study_file(session, accession: str, file_obj: dict, out_dir: Path) -> Path | None:
    fname = file_obj.get("file_name")
    version = file_obj.get("version", 1)
    if not fname:
        return None
    dest = out_dir / fname
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    r = session.get(
        f"{PSI_BASE}/studies/{accession}/download",
        params={"file": fname, "version": version, "redirect": "false"},
        timeout=60,
    )
    if not r.ok or not r.text.strip().startswith("http"):
        print(f"  [warn] presigned URL failed for {accession}/{fname}: {r.status_code}")
        return None
    presigned_url = r.text.strip()
    file_resp = session.get(presigned_url, timeout=120)
    if file_resp.ok:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(file_resp.content)
        return dest
    print(f"  [warn] S3 download failed for {accession}/{fname}: {file_resp.status_code}")
    return None


def main():
    RAW_PSI_DIR.mkdir(parents=True, exist_ok=True)
    details_dir = RAW_PSI_DIR / "investigations"
    tables_dir = RAW_PSI_DIR / "tables"
    details_dir.mkdir(exist_ok=True)
    tables_dir.mkdir(exist_ok=True)

    session = get_session()

    print("1. Searching PSI for combustion investigations...")
    search_url = f"{PSI_BASE}/repo/search?term=combustion&from=0&size=100"
    r = session.get(search_url, timeout=90)
    r.raise_for_status()
    search_data = r.json()
    (RAW_PSI_DIR / "search_combustion.json").write_text(json.dumps(search_data, indent=2))

    hits = search_data.get("hits", {}).get("hits", [])
    print(f"   Found {len(hits)} investigations.")

    summary_rows = []
    for idx, hit in enumerate(hits, 1):
        src = hit.get("_source", {})
        acc = src.get("Accession")
        title = src.get("Title", "")
        if not acc:
            continue

        detail_file = details_dir / f"{acc}.json"
        if detail_file.exists() and detail_file.stat().st_size > 0:
            detail = json.loads(detail_file.read_text())
        else:
            print(f"[{idx}/{len(hits)}] Fetching {acc}: {title[:60]}...")
            dr = session.get(f"{PSI_BASE}/repo/investigations/{acc}", timeout=90)
            if not dr.ok:
                print(f"  [warn] failed detail fetch for {acc}: {dr.status_code}")
                continue
            detail = dr.json()
            detail_file.write_text(json.dumps(detail, indent=2))

        exp_tables = detail.get("experimentalTable") or []
        mod_tables = detail.get("modelingTable") or []
        readmes = detail.get("readme") or []

        downloaded_tables = []
        for tbl in exp_tables + mod_tables + readmes:
            fname = tbl.get("file_name", "")
            # Download only curated experimentalTable, modelingTable, and readme files (< 15 MB)
            fsize = tbl.get("file_size") or 0
            if fsize < 15_000_000:
                saved = download_study_file(session, acc, tbl, tables_dir / acc)
                if saved:
                    downloaded_tables.append(str(saved.relative_to(RAW_PSI_DIR)))

        summary_rows.append(
            {
                "accession": acc,
                "acronym": detail.get("investigationAcronym") or src.get("Acronym", ""),
                "title": detail.get("title") or title,
                "research_area": detail.get("researchArea", ""),
                "sub_research_area": detail.get("subResearchArea", ""),
                "flight_program": detail.get("flightProgram") or src.get("Flight Platform", ""),
                "hardware": detail.get("experimentHardware", ""),
                "doi": detail.get("doi", ""),
                "Start": detail.get("investigationStartDate", ""),
                "End": detail.get("investigationEndDate", ""),
                "num_files_in_repo": len(detail.get("added") or []),
                "downloaded_tables": downloaded_tables,
            }
        )

    (RAW_PSI_DIR / "catalog_summary.json").write_text(json.dumps(summary_rows, indent=2))
    print(f"\nDone! Saved {len(summary_rows)} investigation records to {RAW_PSI_DIR}")
    total_tbls = sum(len(r["downloaded_tables"]) for r in summary_rows)
    print(f"Downloaded {total_tbls} experimental/modeling CSV & text files.")


if __name__ == "__main__":
    main()
