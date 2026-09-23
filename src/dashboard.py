"""Streamlit dashboard for ecom-intel.

Python-only internal dashboard over the knowledge base. Reads from Postgres
when configured, otherwise from the local JSON store.

Run with:  streamlit run src/dashboard.py
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from src.config.settings import settings

st.set_page_config(page_title=settings.DASHBOARD_TITLE, layout="wide")


@st.cache_data(ttl=60)
def load_data() -> dict:
    from src.services.db import memory
    from src.services.storage import store

    pg = memory()
    if pg.enabled:
        return {"source": "postgres", "rows": pg.rank_businesses()}
    records = store.all_records()
    latest: dict[str, dict] = {}
    for r in records:
        prev = latest.get(r.business_id)
        if prev is None or r.last_analysis_date > (prev.get("last_analysis_date") or ""):
            latest[r.business_id] = r.model_dump(mode="json")
    return {"source": "json", "rows": list(latest.values())}


def main() -> None:
    st.title(settings.DASHBOARD_TITLE or "ecom-intel")
    data = load_data()
    rows = data.get("rows", [])
    st.caption(f"Data source: {data.get('source', 'n/a')} • {len(rows)} businesses")

    if not rows:
        st.info("No records yet. Run `python main.py --regions \"Egypt\"` first.")
        return

    st.subheader("Lead pipeline")
    st.dataframe(
        [
            {
                "Business": r.get("name") or r.get("business_name", ""),
                "Region": r.get("region", ""),
                "Industry": r.get("industry", ""),
                "Priority": r.get("lead_priority", ""),
                "Health": r.get("overall_business_health", r.get("business_health", "")),
                "Opportunity": r.get("overall_ai_opportunity", r.get("ai_opportunity", "")),
                "Change": r.get("change_since_previous", ""),
                "AI Summary": (r.get("ai_summary") or "")[:60],
            }
            for r in rows
        ],
        width="stretch",
        hide_index=True,
    )

    st.subheader("Priority summary")
    counts = {}
    for r in rows:
        k = r.get("lead_priority") or r.get("priority") or "n/a"
        counts[k] = counts.get(k, 0) + 1
    st.bar_chart(counts)

    with st.expander("Recent reports"):
        out = Path(settings.OUTPUT_DIR).resolve()
        for p in sorted(out.glob("*.md"), reverse=True)[:10]:
            st.write(f"[{p.name}]({p.as_uri()})")
            if st.button("Show", key=p.name):
                st.text(p.read_text()[:12000])


main()