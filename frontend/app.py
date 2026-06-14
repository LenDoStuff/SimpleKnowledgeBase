from __future__ import annotations

from html import escape
import json
import os
import time
from collections import defaultdict
from typing import Any

import httpx
import streamlit as st


API_BASE_URL = os.getenv("CLAIM_STRUCTURER_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
SUPPORTED_TYPES = ["pdf", "png", "jpg", "jpeg", "docx", "xlsx"]


def render_styles() -> None:
    st.markdown(
        """
        <style>
        :root { color-scheme: light; }
        .stApp {
            background: #f6f8fb;
            color: #1f2937;
        }
        header[data-testid="stHeader"], #MainMenu, footer {
            visibility: hidden;
            height: 0;
        }
        .block-container {
            max-width: 100%;
            padding: 0 18px 18px;
        }
        .app-topbar {
            height: 52px;
            margin: 0 -18px 14px;
            padding: 0 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #ffffff;
            border-bottom: 1px solid #e5e7eb;
        }
        .brand {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 17px;
            font-weight: 750;
            color: #111827;
        }
        .brand-icon {
            width: 27px;
            height: 27px;
            border-radius: 7px;
            display: grid;
            place-items: center;
            background: #2f6fed;
            color: #ffffff;
            font-size: 14px;
            font-weight: 800;
        }
        .help-link {
            color: #64748b;
            font-size: 13px;
        }
        .panel {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 18px;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }
        .side-panel {
            min-height: calc(100vh - 84px);
        }
        .section-title {
            margin: 0 0 14px;
            color: #111827;
            font-size: 15px;
            font-weight: 750;
        }
        .small-muted {
            color: #64748b;
            font-size: 12px;
        }
        .document-row {
            display: grid;
            grid-template-columns: 44px minmax(0, 1fr) 18px;
            gap: 12px;
            align-items: center;
            padding: 10px;
            border: 1px solid #e5e7eb;
            border-radius: 7px;
            background: #ffffff;
            margin-bottom: 9px;
        }
        .document-row.selected {
            border-color: #2f6fed;
            box-shadow: inset 3px 0 0 #2f6fed;
            background: #f8fbff;
        }
        .doc-thumb {
            width: 38px;
            height: 48px;
            border-radius: 4px;
            border: 1px solid #e5e7eb;
            background: linear-gradient(180deg, #ffffff, #f1f5f9);
            position: relative;
        }
        .doc-thumb::before,
        .doc-thumb::after {
            content: "";
            position: absolute;
            left: 8px;
            right: 8px;
            height: 2px;
            background: #cbd5e1;
            border-radius: 999px;
        }
        .doc-thumb::before { top: 14px; }
        .doc-thumb::after { top: 23px; }
        .doc-title {
            margin: 0;
            color: #111827;
            font-size: 13px;
            font-weight: 700;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .doc-meta {
            margin-top: 2px;
            color: #64748b;
            font-size: 12px;
        }
        .doc-status {
            margin-top: 3px;
            color: #16a34a;
            font-size: 11px;
            font-weight: 650;
        }
        .data-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 10px;
        }
        .data-head h2 {
            margin: 0;
            color: #111827;
            font-size: 16px;
            font-weight: 780;
        }
        .data-table {
            width: 100%;
            border-collapse: collapse;
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            overflow: hidden;
            font-size: 13px;
        }
        .data-table th {
            color: #475569;
            font-size: 12px;
            font-weight: 750;
            text-align: left;
            padding: 10px 12px;
            border-bottom: 1px solid #e5e7eb;
            background: #ffffff;
        }
        .data-table td {
            padding: 9px 12px;
            border-bottom: 1px solid #edf2f7;
            color: #1f2937;
            vertical-align: top;
        }
        .data-table tr:last-child td {
            border-bottom: 0;
        }
        .section-row td {
            background: #f2f4f8;
            color: #111827;
            font-weight: 760;
        }
        .source-link {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            max-width: 260px;
            color: #2563eb;
            text-decoration: none;
            font-size: 12px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .source-link:hover {
            text-decoration: underline;
        }
        .validation-note {
            margin-top: 12px;
            color: #64748b;
            font-size: 12px;
        }
        .stDownloadButton button,
        .stButton button {
            border-radius: 6px;
            border: 1px solid #d9e2f0;
            background: #ffffff;
            color: #1f2937;
            font-size: 13px;
            font-weight: 650;
        }
        .stDownloadButton button {
            background: #2f6fed;
            border-color: #2f6fed;
            color: #ffffff;
        }
        div[data-testid="stFileUploader"] {
            border: 1px dashed #cbd5e1;
            border-radius: 8px;
            padding: 14px;
            background: #fbfdff;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def api_error(response: httpx.Response, fallback: str) -> str:
    try:
        payload = response.json()
    except ValueError:
        return fallback
    if isinstance(payload, dict) and payload.get("detail"):
        return str(payload["detail"])
    return fallback


def request_json(method: str, path: str, **kwargs: Any) -> Any:
    response = httpx.request(method, f"{API_BASE_URL}{path}", timeout=120.0, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(api_error(response, "Request failed."))
    return response.json()


def create_job(files: list[Any]) -> dict[str, Any]:
    parts = [("files", (file.name, file.getvalue(), file.type or "application/octet-stream")) for file in files]
    return request_json("POST", "/api/jobs", files=parts)


def load_job(job_id: str) -> None:
    job = request_json("GET", f"/api/jobs/{job_id}")
    st.session_state.job = job
    st.session_state.documents = job.get("files") or []

    if job.get("status") == "complete":
        st.session_state.documents = request_json("GET", f"/api/jobs/{job_id}/documents")
        st.session_state.graph = request_json("GET", f"/api/jobs/{job_id}/graph")
    elif job.get("status") == "failed":
        st.session_state.error = job.get("error") or "Processing failed."


def source_preview(source: dict[str, Any]) -> dict[str, Any] | None:
    response = httpx.get(
        f"{API_BASE_URL}/api/documents/{source['document_id']}/source/{source['id']}",
        timeout=30.0,
    )
    if response.status_code >= 400:
        return None
    return response.json()


def initialize_state() -> None:
    for key, value in {
        "job": None,
        "documents": [],
        "graph": None,
        "error": "",
        "selected_source_id": None,
    }.items():
        st.session_state.setdefault(key, value)


def submit(files: list[Any]) -> None:
    st.session_state.error = ""
    st.session_state.documents = []
    st.session_state.graph = None
    st.session_state.selected_source_id = None
    job = create_job(files)
    st.session_state.job = job
    st.query_params["job"] = job["job_id"]


def money(value: Any) -> str:
    try:
        return f"${float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def graph_documents(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    documents = {document["id"]: document for document in graph.get("documents", [])}
    documents.update({document["id"]: document for document in st.session_state.documents})
    return documents


def graph_sources(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {source["id"]: source for source in graph.get("sources", [])}


def document_url(document: dict[str, Any] | None) -> str:
    content_uri = (document or {}).get("content_uri") or ""
    if content_uri.startswith("/"):
        return f"{API_BASE_URL}{content_uri}"
    return content_uri


def source_badges(source_ids: list[str] | None, graph: dict[str, Any]) -> str:
    if not source_ids:
        return '<span style="color:#9ca3af;">No source</span>'

    documents = graph_documents(graph)
    sources = graph_sources(graph)
    badges = []
    for index, source_id in enumerate(source_ids, start=1):
        source = sources.get(source_id)
        document = documents.get((source or {}).get("document_id"))
        document_name = (document or {}).get("filename") or (document or {}).get("title") or "Document"
        citation = (source or {}).get("citation_text") or "Source text unavailable"
        title = escape(f"{document_name}\n{citation}", quote=True)
        label = escape(document_name)
        url = escape(document_url(document), quote=True)
        if url:
            badges.append(
                f'<a class="source-link" href="{url}" target="_blank" rel="noopener noreferrer" title="{title}">'
                f"{label} &#8599;</a>"
            )
        else:
            badges.append(
                f'<span title="{title}" style="display:inline-block;margin:2px 6px 2px 0;'
                'padding:4px 8px;border:1px solid #6b7280;border-radius:999px;'
                'color:#d1d5db;font-size:0.82rem;">'
                f"{label}</span>"
            )
    return " ".join(badges)


def render_sourced_field(label: str, value: Any, source_ids: list[str] | None, graph: dict[str, Any]) -> None:
    with st.container(border=True):
        field_column, value_column, source_column = st.columns([1.1, 1.5, 1])
        field_column.caption("Field")
        field_column.write(label)
        value_column.caption("Value")
        value_column.write(value or "-")
        source_column.caption("Source")
        source_column.markdown(source_badges(source_ids, graph), unsafe_allow_html=True)


def render_upload() -> None:
    st.markdown('<p class="section-title">1. Upload claim files</p>', unsafe_allow_html=True)
    files = st.file_uploader("Claim files", type=SUPPORTED_TYPES, accept_multiple_files=True, label_visibility="collapsed")
    if st.button("Process files", type="primary", disabled=not files):
        try:
            submit(files)
            st.rerun()
        except (httpx.HTTPError, RuntimeError) as exc:
            st.session_state.error = str(exc)


def render_documents() -> None:
    documents = st.session_state.documents
    st.markdown(f'<p class="section-title">2. Extracted documents <span class="small-muted">({len(documents)})</span></p>', unsafe_allow_html=True)
    if not documents:
        st.caption("Uploaded files will appear here.")
        return

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for document in documents:
        groups[document.get("sort_group") or "Other"].append(document)

    for group, items in groups.items():
        st.markdown(f"**{group}**")
        cards = []
        for index, item in enumerate(items):
            selected = " selected" if index == 0 and group == next(iter(groups)) else ""
            title = escape(str(item.get("filename") or "-"))
            document_type = escape(str(item.get("document_type") or "-"))
            pages = escape(str(item.get("pages") or "-"))
            status = escape(str(item.get("status") or "-").capitalize())
            cards.append(
                f'<div class="document-row{selected}">'
                '<div class="doc-thumb"></div>'
                '<div>'
                f'<p class="doc-title">{title}</p>'
                f'<div class="doc-meta">{document_type} - {pages} page(s)</div>'
                f'<div class="doc-status">{status}</div>'
                '</div>'
                '<div class="small-muted">&gt;</div>'
                '</div>'
            )
        st.markdown("".join(cards), unsafe_allow_html=True)


def render_claim(graph: dict[str, Any]) -> None:
    claim = graph.get("claim", {})
    st.write(claim.get("summary") or "-")
    fields = [
        ("Claim number", claim.get("id")),
        ("Loss date", claim.get("loss_date")),
        ("Line of business", claim.get("line_of_business")),
        ("Status", claim.get("status")),
    ]
    for label, value in fields:
        render_sourced_field(label, value, claim.get("source_ids"), graph)


def render_events(graph: dict[str, Any]) -> None:
    st.dataframe(
        [
            {
                "Date": event.get("event_date") or "-",
                "Type": event.get("event_type"),
                "Summary": event.get("summary"),
                "Sources": ", ".join(event.get("source_ids") or []),
            }
            for event in graph.get("events", [])
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_parties(graph: dict[str, Any]) -> None:
    st.dataframe(
        [
            {
                "Role": party.get("role"),
                "Name": party.get("name"),
                "Type": party.get("party_type"),
                "Sources": ", ".join(party.get("source_ids") or []),
            }
            for party in graph.get("parties", [])
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_financials(graph: dict[str, Any]) -> None:
    items = graph.get("financial_items", [])
    st.metric("Total claimed", money(sum(float(item.get("amount") or 0) for item in items)))
    st.dataframe(
        [
            {
                "Type": item.get("financial_type"),
                "Description": item.get("summary"),
                "Amount": money(item.get("amount")),
                "Date": item.get("booking_date") or "-",
                "Sources": ", ".join(item.get("source_ids") or []),
            }
            for item in items
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_sources(graph: dict[str, Any]) -> None:
    sources = graph.get("sources", [])
    source_ids = [source["id"] for source in sources]
    if not source_ids:
        st.caption("No sources returned.")
        return

    selected = st.selectbox("Inspect source", source_ids)
    source = next(source for source in sources if source["id"] == selected)
    preview = source_preview(source)
    if not preview:
        st.info("Source preview is not available.")
        return

    st.markdown(f"**{preview.get('title', '-') }**")
    st.caption(preview.get("source_id", "-"))
    st.markdown(f"> {preview.get('citation_text') or '-'}")
    preview_url = preview.get("document_preview_url")
    if preview_url:
        url = f"{API_BASE_URL}{preview_url}" if preview_url.startswith("/") else preview_url
        st.link_button("Open document", url)


def table_section(title: str) -> str:
    return f'<tr class="section-row"><td colspan="3">{escape(title)}</td></tr>'


def table_row(field: str, value: Any, source_ids: list[str] | None, graph: dict[str, Any]) -> str:
    return (
        "<tr>"
        f"<td>{escape(field)}</td>"
        f"<td>{escape(str(value or '-'))}</td>"
        f"<td>{source_badges(source_ids, graph)}</td>"
        "</tr>"
    )


def render_extracted_table(graph: dict[str, Any]) -> None:
    claim = graph.get("claim", {})
    source_ids = (claim.get("source_ids") or [])[:1]
    rows = [
        table_section("Claim Information"),
        table_row("Claim Number", claim.get("id"), source_ids, graph),
        table_row("Loss Date", claim.get("loss_date"), source_ids, graph),
        table_row("Line of Business", claim.get("line_of_business"), source_ids, graph),
        table_row("Status", claim.get("status"), source_ids, graph),
        table_row("Summary", claim.get("summary"), source_ids, graph),
    ]

    if graph.get("events"):
        rows.append(table_section("Events"))
        for event in graph["events"]:
            value = f"{event.get('event_date') or 'No date'} - {event.get('summary') or '-'}"
            rows.append(table_row(event.get("event_type") or "Event", value, event.get("source_ids"), graph))

    if graph.get("parties"):
        rows.append(table_section("Parties"))
        for party in graph["parties"]:
            value = f"{party.get('name') or '-'} ({party.get('party_type') or '-'})"
            rows.append(table_row(party.get("role") or "Party", value, party.get("source_ids"), graph))

    if graph.get("financial_items"):
        rows.append(table_section("Financials"))
        for item in graph["financial_items"]:
            amount = f"{money(item.get('amount'))} {item.get('currency') or ''}".strip()
            value = f"{item.get('summary') or '-'} | {amount}"
            if item.get("booking_date"):
                value = f"{value} | {item['booking_date']}"
            rows.append(table_row(item.get("financial_type") or "Financial item", value, item.get("source_ids"), graph))

    st.markdown(
        "<table class=\"data-table\">"
        "<thead><tr><th>Field</th><th>Extracted Data</th><th>Source</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>",
        unsafe_allow_html=True,
    )


def render_output() -> None:
    graph = st.session_state.graph
    if not graph:
        if st.session_state.job:
            st.info("Processing claim files.")
        else:
            st.info("Upload files to generate structured output.")
        return

    render_extracted_table(graph)
    validation = graph.get("validation", {})
    validation_text = "Validation passed." if validation.get("valid") else "Validation pending."
    st.markdown(
        f'<p class="validation-note">{validation_text} Data is extracted using AI and may contain errors. Verify with source documents.</p>',
        unsafe_allow_html=True,
    )


def poll_job() -> None:
    job = st.session_state.job
    if not job or job.get("status") in {"complete", "failed"}:
        return

    time.sleep(1)
    try:
        load_job(job["job_id"])
    except (httpx.HTTPError, RuntimeError) as exc:
        st.session_state.error = str(exc)
    st.rerun()


def main() -> None:
    st.set_page_config(page_title="Claim Structurer", layout="wide")
    render_styles()
    initialize_state()

    job_id = st.query_params.get("job")
    if job_id and not st.session_state.job:
        try:
            load_job(str(job_id))
        except (httpx.HTTPError, RuntimeError) as exc:
            st.session_state.error = str(exc)

    status = (st.session_state.job or {}).get("status", "ready")
    st.markdown(
        '<div class="app-topbar">'
        '<div class="brand"><div class="brand-icon">C</div><span>Claim Structurer</span></div>'
        '<div class="help-link">Help</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Backend: {API_BASE_URL} | Status: {status}")
    if st.session_state.error:
        st.error(st.session_state.error)

    upload_column, output_column = st.columns([1, 2], gap="large")
    with upload_column:
        with st.container(border=True):
            render_upload()
            st.divider()
            render_documents()
    with output_column:
        with st.container(border=True):
            graph = st.session_state.graph
            title_column, action_column = st.columns([1, 0.28])
            title_column.markdown('<p class="section-title">3. Extracted Data</p>', unsafe_allow_html=True)
            if graph:
                action_column.download_button(
                    "Export JSON",
                    data=json.dumps(graph, indent=2),
                    file_name=f"{graph.get('claim', {}).get('id', 'claim')}.json",
                    mime="application/json",
                    use_container_width=True,
                )
            render_output()

    poll_job()


if __name__ == "__main__":
    main()
