"""Gradio web frontend for the Predictive Maintenance system.

Four tabs: Dashboard/Auth, Telemetry Upload, Analytics & Visuals, AI Assistant.
Each browser session gets its own authenticated APIClient held in gr.State.

Run with:  python -m frontend.app
"""

from __future__ import annotations

import os
import time

import gradio as gr
import plotly.graph_objects as go

from frontend.client import APIClient, APIError

STATUS_EMOJI = {"OK": "🟢", "WARNING": "🟡", "CRITICAL": "🔴"}


# --------------------------------------------------------------------------- auth
def do_register(client: APIClient, email, password, full_name):
    client = client or APIClient()
    try:
        client.register(email, password, full_name or None)
        client.login(email, password)
        return (
            client,
            _status_md(f"✅ Registered and logged in as **{email}**."),
            *_post_login(client),
        )
    except APIError as e:
        return client, _status_md(f"❌ {e.detail}"), gr.update(), gr.update(), ""


def do_login(client: APIClient, email, password):
    client = client or APIClient()
    try:
        client.login(email, password)
        return client, _status_md(f"✅ Logged in as **{email}**."), *_post_login(client)
    except APIError as e:
        return client, _status_md(f"❌ {e.detail}"), gr.update(), gr.update(), ""


def do_logout(client: APIClient):
    if client:
        client.logout()
    return (
        APIClient(),
        _status_md("Logged out."),
        gr.update(choices=[], value=None),
        gr.update(choices=[], value=None),
        "",
    )


def _post_login(client: APIClient):
    """Return updates for the two machine dropdowns + dashboard markdown."""
    choices = _machine_choices(client)
    dash = _render_dashboard(client)
    return (
        gr.update(choices=choices, value=choices[0][1] if choices else None),
        gr.update(choices=choices, value=choices[0][1] if choices else None),
        dash,
    )


# ----------------------------------------------------------------------- machines
def _machine_choices(client: APIClient) -> list[tuple[str, str]]:
    if not client or not client.is_authenticated:
        return []
    try:
        machines = client.list_machines()
    except APIError:
        return []
    return [
        (f"{STATUS_EMOJI.get(m['status'], '')} {m['name']} ({m['type']})", m["id"])
        for m in machines
    ]


def _render_dashboard(client: APIClient) -> str:
    if not client or not client.is_authenticated:
        return "_Not logged in._"
    try:
        machines = client.list_machines()
    except APIError as e:
        return f"❌ {e.detail}"
    if not machines:
        return "No machines registered yet. Create one below. 👇"
    lines = ["| Status | Name | Type | Location |", "|---|---|---|---|"]
    for m in machines:
        emoji = STATUS_EMOJI.get(m["status"], "")
        lines.append(
            f"| {emoji} {m['status']} | {m['name']} | {m['type']} | {m.get('location') or '—'} |"
        )
    return "\n".join(lines)


def create_machine(client: APIClient, name, type_, location):
    if not client or not client.is_authenticated:
        return client, _status_md("❌ Please log in first."), gr.update(), gr.update(), ""
    if not name or not type_:
        msg = _status_md("❌ Name and type are required.")
        return client, msg, gr.update(), gr.update(), _render_dashboard(client)
    try:
        client.create_machine(name, type_, location or None)
        msg = f"✅ Machine **{name}** created."
    except APIError as e:
        msg = f"❌ {e.detail}"
    choices = _machine_choices(client)
    return (
        client,
        _status_md(msg),
        gr.update(choices=choices, value=choices[0][1] if choices else None),
        gr.update(choices=choices, value=choices[0][1] if choices else None),
        _render_dashboard(client),
    )


def refresh_dashboard(client: APIClient):
    choices = _machine_choices(client)
    return (
        gr.update(choices=choices, value=choices[0][1] if choices else None),
        gr.update(choices=choices, value=choices[0][1] if choices else None),
        _render_dashboard(client),
    )


# ----------------------------------------------------------------------- upload
def upload_and_track(client: APIClient, machine_id, file_obj, progress=gr.Progress()):
    if not client or not client.is_authenticated:
        return "❌ Please log in first."
    if not machine_id:
        return "❌ Select a machine first."
    if file_obj is None:
        return "❌ Choose a CSV file to upload."

    try:
        progress(0.05, desc="Uploading file...")
        resp = client.upload_csv(machine_id, file_obj.name)
        task_id = resp["task_id"]
    except APIError as e:
        return f"❌ Upload failed: {e.detail}"

    # Poll the background task until it completes.
    deadline = time.time() + 600
    last = {}
    while time.time() < deadline:
        try:
            last = client.get_task(task_id)
        except APIError as e:
            return f"❌ {e.detail}"
        status = last["status"]
        rows = last.get("rows_processed", 0)
        anomalies = last.get("anomalies_detected", 0)
        if status in ("COMPLETED", "FAILED"):
            break
        progress(0.5, desc=f"{status}: {rows:,} rows, {anomalies:,} anomalies")
        time.sleep(1.0)

    if last.get("status") == "COMPLETED":
        return (
            f"✅ **Completed.** Processed {last['rows_processed']:,} rows, "
            f"detected {last['anomalies_detected']:,} anomalies.\n\n"
            "Switch to the **Analytics** tab to visualise the results."
        )
    if last.get("status") == "FAILED":
        return f"❌ **Failed:** {last.get('error_message', 'unknown error')}"
    return "⏳ Still processing — check back shortly."


# ----------------------------------------------------------------------- analytics
def _empty_fig(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font={"size": 16})
    fig.update_layout(template="plotly_white", height=300)
    return fig


def render_charts(client: APIClient, machine_id):
    if not client or not client.is_authenticated:
        return _empty_fig("Please log in."), _empty_fig("Please log in."), "—"
    if not machine_id:
        return _empty_fig("Select a machine."), _empty_fig("Select a machine."), "—"
    try:
        series = client.get_series(machine_id, limit=10000)
        summary = client.machine_summary(machine_id)
    except APIError as e:
        return _empty_fig(e.detail), _empty_fig(e.detail), f"❌ {e.detail}"

    ts = series["timestamps"]
    if not ts:
        return (
            _empty_fig("No telemetry yet. Upload a CSV first."),
            _empty_fig("No telemetry yet."),
            "No data.",
        )
    is_anom = series["is_anomaly"]
    anom_idx = [i for i, a in enumerate(is_anom) if a]

    temp_fig = _metric_figure(ts, series["temperature"], anom_idx, "Temperature", "#e74c3c")
    vib_fig = _metric_figure(ts, series["vibration"], anom_idx, "Vibration", "#2980b9")

    md = (
        f"### {summary['name']} — {STATUS_EMOJI.get(summary['status'], '')} {summary['status']}\n"
        f"- **Total readings:** {summary['telemetry_count']:,}\n"
        f"- **Anomalies:** {summary['anomaly_count']:,}\n"
        f"- **Last reading:** {summary.get('last_reading_at') or '—'}"
    )
    return temp_fig, vib_fig, md


def _metric_figure(ts, values, anom_idx, title, color) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=ts, y=values, mode="lines", name=title, line={"color": color, "width": 1.5})
    )
    if anom_idx:
        fig.add_trace(
            go.Scatter(
                x=[ts[i] for i in anom_idx],
                y=[values[i] for i in anom_idx],
                mode="markers",
                name="Anomaly",
                marker={"color": "red", "size": 7, "symbol": "x"},
            )
        )
    fig.update_layout(
        title=title,
        template="plotly_white",
        height=350,
        margin={"l": 40, "r": 20, "t": 40, "b": 30},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
    )
    return fig


# ----------------------------------------------------------------------- ai
def run_ai(client: APIClient, machine_id, window):
    if not client or not client.is_authenticated:
        return "❌ Please log in first."
    if not machine_id:
        return "❌ Select a machine first."
    try:
        r = client.explain(machine_id, int(window))
    except APIError as e:
        return f"❌ {e.detail}"

    badge = "🤖 *mock explainer*" if r["is_mock"] else f"🧠 *{r['model_used']}*"
    recs = "\n".join(f"- {rec}" for rec in r["recommendations"])
    return (
        f"## Maintenance Report — {r['machine_name']} {badge}\n\n"
        f"**Status:** {STATUS_EMOJI.get(r['machine_status'], '')} {r['machine_status']}  |  "
        f"**Window:** {r['window_analyzed']} readings  |  "
        f"**Anomalies:** {r['anomalies_found']}\n\n"
        f"### Summary\n{r['summary']}\n\n"
        f"### Explanation\n{r['explanation']}\n\n"
        f"### Recommendations\n{recs}"
    )


def _status_md(text: str) -> str:
    return text


# --------------------------------------------------------------------------- UI
def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Predictive Maintenance", theme=gr.themes.Soft()) as demo:
        client_state = gr.State(value=None)

        gr.Markdown("# 🛠️ Predictive Maintenance Platform")

        with gr.Tabs():  # noqa: SIM117 - Gradio layout contexts nest idiomatically
            # ---- Tab 1: Dashboard & Auth ----
            with gr.Tab("Dashboard & Auth"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Account")
                        email_in = gr.Textbox(label="Email", placeholder="you@example.com")
                        pw_in = gr.Textbox(label="Password", type="password")
                        name_in = gr.Textbox(label="Full name (register only)")
                        with gr.Row():
                            login_btn = gr.Button("Log in", variant="primary")
                            register_btn = gr.Button("Register")
                        logout_btn = gr.Button("Log out", size="sm")
                        auth_status = gr.Markdown("_Not logged in._")
                    with gr.Column(scale=2):
                        gr.Markdown("### Registered Machines")
                        dashboard_md = gr.Markdown("_Log in to view machines._")
                        refresh_btn = gr.Button("🔄 Refresh", size="sm")
                        gr.Markdown("### Register a New Machine")
                        with gr.Row():
                            m_name = gr.Textbox(label="Name", scale=2)
                            m_type = gr.Textbox(
                                label="Type", placeholder="pump / motor / turbine", scale=2
                            )
                            m_loc = gr.Textbox(label="Location", scale=2)
                        create_btn = gr.Button("➕ Create Machine", variant="primary")

            # ---- Tab 2: Telemetry Upload ----
            with gr.Tab("Telemetry Upload"):
                gr.Markdown(
                    "Upload a sensor CSV (columns: `timestamp, temperature, vibration, "
                    "pressure, rotational_speed`). Large files are streamed and processed "
                    "in chunks."
                )
                upload_machine = gr.Dropdown(label="Machine", choices=[], interactive=True)
                csv_file = gr.File(label="Sensor CSV", file_types=[".csv"])
                upload_btn = gr.Button("⬆️ Upload & Process", variant="primary")
                upload_status = gr.Markdown()

            # ---- Tab 3: Analytics & Visuals ----
            with gr.Tab("Analytics & Visuals"):
                with gr.Row():
                    analytics_machine = gr.Dropdown(label="Machine", choices=[], interactive=True)
                    load_charts_btn = gr.Button("📊 Load Charts", variant="primary")
                analytics_summary = gr.Markdown("—")
                temp_plot = gr.Plot(label="Temperature")
                vib_plot = gr.Plot(label="Vibration")

            # ---- Tab 4: AI Assistant ----
            with gr.Tab("AI Assistant"):
                gr.Markdown(
                    "Generate an AI-powered maintenance report. Uses OpenRouter "
                    "(Gemini) when configured, otherwise a built-in rule-based explainer."
                )
                with gr.Row():
                    ai_machine = gr.Dropdown(label="Machine", choices=[], interactive=True)
                    ai_window = gr.Slider(
                        label="Readings to analyse", minimum=10, maximum=5000, value=500, step=10
                    )
                ai_btn = gr.Button("🧠 Generate Report", variant="primary")
                ai_output = gr.Markdown()

        # The upload/analytics/ai machine dropdowns are kept in sync after every
        # auth / create / refresh action via the .then(...) callbacks below.

        # --- wiring: auth ---
        login_btn.click(
            do_login,
            [client_state, email_in, pw_in],
            [client_state, auth_status, upload_machine, analytics_machine, dashboard_md],
        ).then(_sync_third_dropdown, [client_state], [ai_machine])

        register_btn.click(
            do_register,
            [client_state, email_in, pw_in, name_in],
            [client_state, auth_status, upload_machine, analytics_machine, dashboard_md],
        ).then(_sync_third_dropdown, [client_state], [ai_machine])

        logout_btn.click(
            do_logout,
            [client_state],
            [client_state, auth_status, upload_machine, analytics_machine, dashboard_md],
        ).then(_sync_third_dropdown, [client_state], [ai_machine])

        create_btn.click(
            create_machine,
            [client_state, m_name, m_type, m_loc],
            [client_state, auth_status, upload_machine, analytics_machine, dashboard_md],
        ).then(_sync_third_dropdown, [client_state], [ai_machine])

        refresh_btn.click(
            refresh_dashboard,
            [client_state],
            [upload_machine, analytics_machine, dashboard_md],
        ).then(_sync_third_dropdown, [client_state], [ai_machine])

        # --- wiring: features ---
        upload_btn.click(
            upload_and_track,
            [client_state, upload_machine, csv_file],
            [upload_status],
        )
        load_charts_btn.click(
            render_charts,
            [client_state, analytics_machine],
            [temp_plot, vib_plot, analytics_summary],
        )
        ai_btn.click(run_ai, [client_state, ai_machine, ai_window], [ai_output])

    return demo


def _sync_third_dropdown(client: APIClient):
    choices = _machine_choices(client)
    return gr.update(choices=choices, value=choices[0][1] if choices else None)


def main() -> None:
    host = os.getenv("FRONTEND_HOST", "0.0.0.0")
    port = int(os.getenv("FRONTEND_PORT", "7860"))
    build_ui().queue().launch(server_name=host, server_port=port)


if __name__ == "__main__":
    main()
