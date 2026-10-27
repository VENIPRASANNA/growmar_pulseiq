
import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

# =========================================================
# GROWMAR PHASE 2 - TASK 8: TEAM PRODUCTIVITY DASHBOARD
# =========================================================

st.set_page_config(
    page_title="Team Productivity | PulseIQ",
    page_icon="📊",
    layout="wide",
)

DB_PATH = "05_Starter/pulseiq.duckdb"

st.title("Team Productivity Dashboard")
st.caption(
    "GROWMAR • Phase 2 • Task 8 | Team delivery, sprint velocity, "
    "cycle time, on-time delivery, blocked work and reopened tasks"
)

st.write(
    "Compare team delivery across sprints, investigate workflow issues, "
    "and verify metrics against the underlying task records."
)

# =========================================================
# LOAD DATA
# =========================================================

@st.cache_data(ttl=60)
def load_data():
    con = duckdb.connect(DB_PATH, read_only=True)

    try:
        tasks = con.execute("""
            SELECT
                t.task_id,
                t.team_id,
                t.sprint_id,
                t.assignee_employee_id,
                t.task_type,
                t.priority,
                t.story_points,
                t.created_date,
                t.started_date,
                t.due_date,
                t.completed_date,
                t.status,
                t.reopened_count,
                t.is_overdue_at_cutoff,
                t.completed_on_time,

                tm.team_name,
                tm.active_members,

                s.sprint_name,
                s.start_date AS sprint_start,
                s.end_date AS sprint_end,
                s.working_days,

                CASE
                    WHEN LOWER(t.status) = 'done'
                     AND t.started_date IS NOT NULL
                     AND t.completed_date IS NOT NULL
                     AND t.completed_date >= t.started_date
                    THEN DATE_DIFF(
                        'day',
                        t.started_date,
                        t.completed_date
                    )
                    ELSE NULL
                END AS cycle_days

            FROM raw.fact_task AS t

            LEFT JOIN raw.dim_team AS tm
                ON t.team_id = tm.team_id

            LEFT JOIN raw.dim_sprint AS s
                ON t.sprint_id = s.sprint_id
        """).fetchdf()
    finally:
        con.close()

    for column in [
        "created_date",
        "started_date",
        "due_date",
        "completed_date",
        "sprint_start",
        "sprint_end",
    ]:
        tasks[column] = pd.to_datetime(
            tasks[column],
            errors="coerce",
        )

    tasks["status_norm"] = (
        tasks["status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    tasks["story_points"] = pd.to_numeric(
        tasks["story_points"],
        errors="coerce",
    )

    tasks["reopened_count"] = pd.to_numeric(
        tasks["reopened_count"],
        errors="coerce",
    ).fillna(0)

    tasks["cycle_days"] = pd.to_numeric(
        tasks["cycle_days"],
        errors="coerce",
    )

    tasks["is_done"] = tasks["status_norm"].eq("done")
    tasks["is_cancelled"] = tasks["status_norm"].eq("cancelled")
    tasks["is_blocked"] = tasks["status_norm"].eq("blocked")
    tasks["is_reopened"] = tasks["reopened_count"] > 0

    tasks["valid_cycle_time"] = (
        tasks["is_done"]
        & tasks["started_date"].notna()
        & tasks["completed_date"].notna()
        & (tasks["completed_date"] >= tasks["started_date"])
        & tasks["cycle_days"].notna()
    )

    on_time_flag = (
        tasks["completed_on_time"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    tasks["on_time_yes"] = tasks["is_done"] & on_time_flag.eq("Y")
    tasks["on_time_no"] = tasks["is_done"] & on_time_flag.eq("N")
    tasks["on_time_missing"] = tasks["is_done"] & on_time_flag.eq("")

    return tasks


# IMPORTANT: Assign df before referencing df anywhere else.
try:
    df = load_data()
except Exception as exc:
    st.error(f"Unable to load the task data: {exc}")
    st.info(
        "Run the app from the project root and verify that "
        "05_Starter/pulseiq.duckdb exists."
    )
    st.stop()

if df.empty:
    st.warning("The task table contains no records.")
    st.stop()

# =========================================================
# METRIC CALCULATIONS
# =========================================================

def summarize(group):
    done = group[group["is_done"]]
    eligible = group[~group["is_cancelled"]]
    valid_cycle = done[done["valid_cycle_time"]]

    completed_count = len(done)
    eligible_count = len(eligible)

    on_time_count = int(group["on_time_yes"].sum())

    return pd.Series({
        "task_count": len(group),
        "eligible_tasks": eligible_count,
        "completed_tasks": completed_count,

        "completion_rate_pct": (
            100.0 * completed_count / eligible_count
            if eligible_count else float("nan")
        ),

        "velocity_points": done["story_points"].sum(min_count=1),

        "average_cycle_days": (
            valid_cycle["cycle_days"].mean()
            if not valid_cycle.empty else float("nan")
        ),

        "valid_cycle_tasks": len(valid_cycle),
        "on_time_tasks": on_time_count,
        "late_tasks": int(group["on_time_no"].sum()),
        "missing_on_time_flag": int(group["on_time_missing"].sum()),

        "on_time_rate_pct": (
            100.0 * on_time_count / completed_count
            if completed_count else float("nan")
        ),

        "blocked_tasks": int(group["is_blocked"].sum()),
        "reopened_tasks": int(group["is_reopened"].sum()),
        "reopen_events": int(group["reopened_count"].sum()),
        "cancelled_tasks": int(group["is_cancelled"].sum()),
    })


def grouped_summary(data, columns):
    if data.empty:
        return pd.DataFrame()

    rows = []

    for key, group in data.groupby(columns, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)

        row = dict(zip(columns, key))
        row.update(summarize(group).to_dict())
        rows.append(row)

    return pd.DataFrame(rows)


# =========================================================
# SIDEBAR FILTERS
# =========================================================

st.sidebar.header("Dashboard filters")

team_lookup = (
    df[["team_id", "team_name"]]
    .dropna(subset=["team_name"])
    .drop_duplicates()
    .sort_values("team_name")
)

team_names = team_lookup["team_name"].tolist()

selected_teams = st.sidebar.multiselect(
    "Teams",
    options=team_names,
    default=team_names,
)

sprint_lookup = (
    df[["sprint_id", "sprint_name", "sprint_start"]]
    .dropna(subset=["sprint_id"])
    .drop_duplicates(subset=["sprint_id"])
    .sort_values(["sprint_start", "sprint_id"])
)

sprint_ids = sprint_lookup["sprint_id"].tolist()
sprint_names = dict(
    zip(sprint_lookup["sprint_id"], sprint_lookup["sprint_name"])
)

sprint_options = ["All sprints"] + sprint_ids

selected_sprint = st.sidebar.selectbox(
    "Sprint",
    sprint_options,
    format_func=lambda value: (
        "All sprints"
        if value == "All sprints"
        else f"{value} — {sprint_names.get(value, value)}"
    ),
)

st.sidebar.divider()
st.sidebar.caption(
    "Cancelled tasks are excluded from the completion-rate denominator "
    "and reported separately."
)

filtered = df[df["team_name"].isin(selected_teams)].copy()

if selected_sprint != "All sprints":
    filtered = filtered[filtered["sprint_id"] == selected_sprint]

if filtered.empty:
    st.warning("No tasks match the selected filters.")
    st.stop()

# =========================================================
# KPI CARDS
# =========================================================

overall = summarize(filtered)

k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("Tasks", f"{int(overall['task_count']):,}")
k2.metric("Completed", f"{int(overall['completed_tasks']):,}")

completion_rate = overall["completion_rate_pct"]
k3.metric(
    "Completion rate",
    f"{completion_rate:.2f}%" if pd.notna(completion_rate) else "N/A",
)

k4.metric("Blocked", f"{int(overall['blocked_tasks']):,}")
k5.metric("Reopened tasks", f"{int(overall['reopened_tasks']):,}")

st.caption(
    f"Selected scope: {filtered['team_id'].nunique()} teams · "
    f"{filtered['sprint_id'].nunique()} sprints · "
    f"{int(overall['eligible_tasks']):,} non-cancelled tasks · "
    f"{int(overall['cancelled_tasks']):,} cancelled tasks"
)

# =========================================================
# AGGREGATIONS
# =========================================================

team_sprint = grouped_summary(
    filtered,
    [
        "team_id",
        "team_name",
        "sprint_id",
        "sprint_name",
        "sprint_start",
        "sprint_end",
    ],
)

team_totals = grouped_summary(
    filtered,
    ["team_id", "team_name"],
)

if not team_sprint.empty:
    team_sprint = team_sprint.sort_values(
        ["sprint_start", "team_name"]
    )

if not team_totals.empty:
    team_totals = team_totals.sort_values("team_name")

# =========================================================
# METRIC DEFINITIONS
# =========================================================

with st.expander("Metric definitions and calculation rules", expanded=True):
    st.markdown("""
    **1. Velocity**

    Sum of story points for tasks whose status is `Done`, grouped by
    team and sprint. Unfinished and cancelled tasks contribute no
    completed story points.

    **2. Cycle time**

    Average calendar days between `started_date` and `completed_date`
    for completed tasks with both dates present and completion on or
    after the start date. Calculated using DuckDB `DATE_DIFF('day', ...)`
    to match the official metric definition.

    **3. On-time delivery rate**

    Completed tasks marked `Y` in `completed_on_time`, divided by all
    completed tasks, multiplied by 100. Missing flags remain in the
    denominator and are disclosed separately.

    **4. Task completion rate**

    Done tasks divided by all tasks except Cancelled tasks, multiplied
    by 100.

    **5. Blocked work**

    Count of tasks whose recorded status is `Blocked`. This does not
    measure historical time spent blocked.

    **6. Reopened work**

    Reopened task count is the number of tasks with `reopened_count > 0`.
    Reopen events are the sum of `reopened_count`.

    **7. Cancelled work**

    Count of tasks whose status is `Cancelled`. Cancelled tasks are
    excluded from the completion-rate denominator.

    **Comparison caution:** Team size, work type, story-point practices,
    and sprint duration can affect comparisons. Velocity is not a direct
    measure of individual productivity.
    """)

# =========================================================
# 1. TEAM COMPARISON
# =========================================================

st.header("1. Team comparison")

metric_options = [
    "Velocity (story points)",
    "Average cycle time (days)",
    "On-time delivery rate (%)",
    "Task completion rate (%)",
    "Blocked tasks",
    "Reopened tasks",
]

metric_map = {
    "Velocity (story points)": ("velocity_points", "Story points"),
    "Average cycle time (days)": ("average_cycle_days", "Calendar days"),
    "On-time delivery rate (%)": ("on_time_rate_pct", "Percent"),
    "Task completion rate (%)": ("completion_rate_pct", "Percent"),
    "Blocked tasks": ("blocked_tasks", "Tasks"),
    "Reopened tasks": ("reopened_tasks", "Tasks"),
}

metric_choice = st.selectbox(
    "Choose a team comparison metric",
    metric_options,
)

metric_column, axis_label = metric_map[metric_choice]

chart_df = (
    team_totals.copy()
    if selected_sprint == "All sprints"
    else team_sprint.copy()
)

chart_df[metric_column] = pd.to_numeric(
    chart_df[metric_column],
    errors="coerce",
)
chart_df = chart_df.dropna(subset=[metric_column])

if not chart_df.empty:
    fig = px.bar(
        chart_df,
        x="team_name",
        y=metric_column,
        color="team_name",
        hover_data=["team_id"],
        title=metric_choice,
        labels={
            "team_name": "Team",
            metric_column: axis_label,
        },
    )
    fig.update_layout(
        showlegend=False,
        xaxis_tickangle=-35,
        height=480,
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No eligible data is available for this metric.")

# =========================================================
# 2. SPRINT-BY-SPRINT TRENDS
# =========================================================

st.header("2. Sprint-by-sprint trends")

trend_options = [
    "Velocity (story points)",
    "Average cycle time (days)",
    "On-time delivery rate (%)",
]

trend_metric = st.selectbox(
    "Choose a trend metric",
    trend_options,
    key="trend_metric",
)

trend_column, trend_axis = metric_map[trend_metric]

trend_df = team_sprint.dropna(subset=[trend_column]).copy()

if not trend_df.empty:
    fig = px.line(
        trend_df.sort_values(["sprint_start", "team_name"]),
        x="sprint_name",
        y=trend_column,
        color="team_name",
        markers=True,
        hover_data=["team_id", "sprint_id"],
        title=f"{trend_metric} by sprint",
        labels={
            "sprint_name": "Sprint",
            trend_column: trend_axis,
            "team_name": "Team",
        },
    )
    fig.update_layout(
        height=500,
        xaxis_tickangle=-35,
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No data is available for this trend.")

# =========================================================
# 3. BLOCKED, REOPENED AND CANCELLED WORK
# =========================================================

st.header("3. Blocked and reopened work")

if not team_totals.empty:
    work_long = team_totals.melt(
        id_vars=["team_name"],
        value_vars=[
            "blocked_tasks",
            "reopened_tasks",
            "cancelled_tasks",
        ],
        var_name="work_type",
        value_name="work_count",
    )

    work_labels = {
        "blocked_tasks": "Blocked",
        "reopened_tasks": "Reopened at least once",
        "cancelled_tasks": "Cancelled",
    }

    work_long["work_type"] = work_long["work_type"].map(work_labels)

    fig = px.bar(
        work_long,
        x="team_name",
        y="work_count",
        color="work_type",
        barmode="group",
        title="Blocked, reopened and cancelled tasks by team",
        labels={
            "team_name": "Team",
            "work_count": "Task count",
            "work_type": "Work category",
        },
    )
    fig.update_layout(height=480, xaxis_tickangle=-35)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Reopen events by team")

    reopen_df = team_totals.sort_values(
        "reopen_events",
        ascending=False,
    )

    fig = px.bar(
        reopen_df,
        x="team_name",
        y="reopen_events",
        hover_data=["reopened_tasks"],
        title="Total reopen events",
        labels={
            "team_name": "Team",
            "reopen_events": "Reopen events",
        },
    )
    fig.update_layout(height=400, xaxis_tickangle=-35)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No team-level workflow data is available.")

# =========================================================
# 4. TEAM AND SPRINT DETAIL
# =========================================================

st.header("4. Team and sprint detail")

detail_columns = [
    "team_name",
    "team_id",
    "sprint_name",
    "sprint_id",
    "task_count",
    "eligible_tasks",
    "completed_tasks",
    "completion_rate_pct",
    "velocity_points",
    "average_cycle_days",
    "valid_cycle_tasks",
    "on_time_tasks",
    "late_tasks",
    "missing_on_time_flag",
    "on_time_rate_pct",
    "blocked_tasks",
    "reopened_tasks",
    "reopen_events",
    "cancelled_tasks",
]

detail = team_sprint[detail_columns].copy()

detail = detail.rename(columns={
    "team_name": "Team",
    "team_id": "Team ID",
    "sprint_name": "Sprint",
    "sprint_id": "Sprint ID",
    "task_count": "All tasks",
    "eligible_tasks": "Eligible tasks",
    "completed_tasks": "Completed",
    "completion_rate_pct": "Completion rate %",
    "velocity_points": "Velocity points",
    "average_cycle_days": "Average cycle days",
    "valid_cycle_tasks": "Valid cycle-time tasks",
    "on_time_tasks": "On-time tasks",
    "late_tasks": "Late tasks",
    "missing_on_time_flag": "Missing on-time flags",
    "on_time_rate_pct": "On-time rate %",
    "blocked_tasks": "Blocked",
    "reopened_tasks": "Reopened tasks",
    "reopen_events": "Reopen events",
    "cancelled_tasks": "Cancelled",
})

st.dataframe(
    detail,
    use_container_width=True,
    hide_index=True,
)

st.download_button(
    "Download team and sprint metrics (CSV)",
    data=detail.to_csv(index=False).encode("utf-8"),
    file_name="team_productivity_metrics.csv",
    mime="text/csv",
)

# =========================================================
# 5. TWO-TEAM VERIFICATION
# =========================================================

st.header("5. Manual verification — two teams")

st.write(
    "Choose two teams and inspect calculations based on their raw task "
    "records. The verification uses the current sprint filter, if selected."
)

available_teams = team_totals["team_name"].dropna().tolist()

if len(available_teams) >= 2:
    col_a, col_b = st.columns(2)

    with col_a:
        verify_a = st.selectbox(
            "Team A",
            available_teams,
            index=0,
            key="verify_team_a",
        )

    with col_b:
        verify_b = st.selectbox(
            "Team B",
            available_teams,
            index=1,
            key="verify_team_b",
        )

    verify_df = filtered[
        filtered["team_name"].isin([verify_a, verify_b])
    ].copy()

    verification_rows = []

    for team_name in [verify_a, verify_b]:
        group = verify_df[verify_df["team_name"] == team_name]
        metrics = summarize(group)

        verification_rows.append({
            "Team": team_name,
            "Raw task rows": len(group),
            "Done tasks": int(metrics["completed_tasks"]),
            "Cancelled tasks": int(metrics["cancelled_tasks"]),
            "Eligible tasks": int(metrics["eligible_tasks"]),
            "Completion rate %": (
                round(metrics["completion_rate_pct"], 2)
                if pd.notna(metrics["completion_rate_pct"]) else None
            ),
            "Completed story points": metrics["velocity_points"],
            "Valid cycle-time tasks": int(metrics["valid_cycle_tasks"]),
            "Average cycle days": (
                round(metrics["average_cycle_days"], 2)
                if pd.notna(metrics["average_cycle_days"]) else None
            ),
            "On-time tasks": int(metrics["on_time_tasks"]),
            "Late tasks": int(metrics["late_tasks"]),
            "Missing on-time flags": int(
                metrics["missing_on_time_flag"]
            ),
            "On-time rate %": (
                round(metrics["on_time_rate_pct"], 2)
                if pd.notna(metrics["on_time_rate_pct"]) else None
            ),
            "Blocked tasks": int(metrics["blocked_tasks"]),
            "Reopened tasks": int(metrics["reopened_tasks"]),
            "Reopen events": int(metrics["reopen_events"]),
        })

    verification_table = pd.DataFrame(verification_rows)

    st.dataframe(
        verification_table,
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "Download verification table (CSV)",
        data=verification_table.to_csv(index=False).encode("utf-8"),
        file_name="team_productivity_verification.csv",
        mime="text/csv",
    )
else:
    st.info("At least two teams are required for verification.")

# =========================================================
# 6. THREE NUMERICAL FINDINGS
# =========================================================

st.header("6. Findings about team health")

completed_teams = team_totals[
    team_totals["completed_tasks"] > 0
].copy()

if not completed_teams.empty:
    highest_velocity = completed_teams.loc[
        completed_teams["velocity_points"].idxmax()
    ]

    st.markdown("**Finding 1 — Completed story-point volume**")
    st.write(
        f"{highest_velocity['team_name']} recorded "
        f"{highest_velocity['velocity_points']:.0f} completed story points "
        f"from {int(highest_velocity['completed_tasks'])} completed tasks "
        "in the selected scope. This measures delivery volume, not "
        "necessarily superior productivity."
    )

    highest_reopened = team_totals.loc[
        team_totals["reopened_tasks"].idxmax()
    ]

    st.markdown("**Finding 2 — Reopened work**")
    st.write(
        f"{highest_reopened['team_name']} had "
        f"{int(highest_reopened['reopened_tasks'])} tasks reopened at "
        f"least once and {int(highest_reopened['reopen_events'])} total "
        "reopen events. This warrants investigation alongside task mix "
        "and delivery context; it does not establish a cause."
    )

    cycle_candidates = completed_teams.dropna(
        subset=["average_cycle_days"]
    )

    on_time_candidates = completed_teams.dropna(
        subset=["on_time_rate_pct"]
    )

    highest_blocked = team_totals.loc[
        team_totals["blocked_tasks"].idxmax()
    ]

    finding_parts = []

    if not cycle_candidates.empty:
        fastest = cycle_candidates.loc[
            cycle_candidates["average_cycle_days"].idxmin()
        ]
        finding_parts.append(
            f"{fastest['team_name']} had the lowest average valid cycle "
            f"time ({fastest['average_cycle_days']:.2f} calendar days)"
        )

    if not on_time_candidates.empty:
        best_on_time = on_time_candidates.loc[
            on_time_candidates["on_time_rate_pct"].idxmax()
        ]
        finding_parts.append(
            f"{best_on_time['team_name']} had the highest recorded "
            f"on-time delivery rate ({best_on_time['on_time_rate_pct']:.2f}%)"
        )

    finding_parts.append(
        f"{highest_blocked['team_name']} had the most blocked tasks "
        f"({int(highest_blocked['blocked_tasks'])})"
    )

    st.markdown("**Finding 3 — Delivery and flow health**")
    st.write(
        ". ".join(finding_parts)
        + ". These measures describe different dimensions of team health."
    )
else:
    st.info("No teams with completed tasks are available in this scope.")

# =========================================================
# 7. DATA QUALITY NOTES
# =========================================================

st.header("7. Data quality and interpretation")

done_rows = filtered[filtered["is_done"]]

missing_flags = int(done_rows["on_time_missing"].sum())
invalid_cycle = int((~done_rows["valid_cycle_time"]).sum())

st.write(
    f"- {missing_flags:,} completed tasks in the selected scope have "
    "a missing on-time flag. They remain in the on-time denominator."
)

st.write(
    f"- {invalid_cycle:,} completed tasks in the selected scope lack "
    "a valid start/completion date pair and are excluded from the "
    "cycle-time average."
)

st.write(
    "- Blocked counts describe the recorded current task status, "
    "not historical blocked periods."
)

st.write(
    "- Team comparisons should account for team size, work mix, "
    "story-point conventions and sprint length."
)

st.success("Team Productivity Dashboard loaded successfully.")
