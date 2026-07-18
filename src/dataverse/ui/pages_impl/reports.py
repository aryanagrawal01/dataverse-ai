"""Reports page: generate PDF, download, history of past reports."""

import streamlit as st

from dataverse.schemas.auth import UserDTO
from dataverse.services import report_service
from dataverse.utils.errors import DataVerseError


def render(user: UserDTO, project_id: str) -> None:
    st.markdown("##### Executive report")
    st.caption(
        "A polished PDF with the executive summary, key metrics, dashboard "
        "highlights, AI insights, and the full cleaning audit log."
    )

    if st.button("📄 Generate PDF report", type="primary"):
        try:
            with st.spinner("Building your report (rendering charts)…"):
                handle = report_service.generate_pdf(user.id, project_id)
        except DataVerseError as exc:
            st.error(exc.user_message)
            return
        st.session_state["dv_last_report"] = {
            "filename": handle.filename,
            "data": handle.data,
        }
        st.success("Report ready.")

    last = st.session_state.get("dv_last_report")
    if last:
        st.download_button(
            f"⬇ Download {last['filename']}",
            data=last["data"],
            file_name=last["filename"],
            mime="application/pdf",
            use_container_width=True,
        )

    try:
        past = report_service.list_reports(user.id, project_id)
    except DataVerseError:
        past = []
    if past:
        st.divider()
        st.markdown("##### Past reports")
        for r in past[:10]:
            col_info, col_dl = st.columns([4, 1.4])
            with col_info:
                st.markdown(f"`{r['created_at']:%Y-%m-%d %H:%M}` · {r['size_bytes'] / 1024:.0f} KB")
            with col_dl:
                if st.button("Download", key=f"dl_{r['id']}", use_container_width=True):
                    try:
                        data = report_service.download_report(user.id, project_id, r["id"])
                    except DataVerseError as exc:
                        st.error(exc.user_message)
                    else:
                        st.session_state["dv_last_report"] = {
                            "filename": "DataVerse Report.pdf",
                            "data": data,
                        }
                        st.rerun()
