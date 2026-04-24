"""
app.py  –  Flask web front-end for CampusCopilot (student-facing).
Run:  python app.py   (from project root)
"""

from __future__ import annotations

import os
import re
import sys
import time
from datetime import timedelta

from flask import Flask, jsonify, render_template, request, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.campus_map import generate_campus_map
from src.chatbot import Chatbot
from src.data_loader import load_events, load_finance, load_schedule, load_students
from src.fees import (
    BRANCH_TUITION,
    COMMON_FEES,
    HOSTEL_TIERS,
    HOSTEL_SEMESTER_TOTAL,
    PAYMENT_NOTE,
    compute_semester_total,
)
from src.main import build_handlers

# ---------------------------------------------------------------------------
# App & output directory
# ---------------------------------------------------------------------------
app = Flask(__name__)
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Load data once at startup
# ---------------------------------------------------------------------------
students    = load_students()
events      = load_events()
finance_df  = load_finance()
schedule_df = load_schedule()

# ---------------------------------------------------------------------------
# Jinja2 filters
# ---------------------------------------------------------------------------
@app.template_filter("currency")
def currency_filter(amount: float) -> str:
    return f"₹{amount:,.0f}"


@app.template_filter("fmtdate")
def fmtdate_filter(val) -> str:
    try:
        return val.strftime("%d %b %Y")
    except Exception:
        return str(val)


# ---------------------------------------------------------------------------
# Exam-event collision helpers
# ---------------------------------------------------------------------------
def _build_conflicts(evts, sched_df):
    """
    Returns {event_id: [conflict_dict, ...]} for same-day and day-before clashes.
    """
    conflicts: dict = {}
    for ev in evts:
        ev_date = ev.date.date()
        clashes = []
        for _, exam in sched_df.iterrows():
            exam_date  = exam["Date"].date()
            exam_type  = exam["ExamType"]
            exam_subj  = exam["Subject"]
            exam_dept  = exam["Department"]
            exam_time  = f"{exam['StartTime']}–{exam['EndTime']}"
            if ev_date == exam_date:
                clashes.append({
                    "kind": "same_day",
                    "exam_type": exam_type,
                    "subject":   exam_subj,
                    "dept":      exam_dept,
                    "time":      exam_time,
                    "date":      exam_date,
                })
            elif ev_date == exam_date - timedelta(days=1):
                clashes.append({
                    "kind": "day_before",
                    "exam_type": exam_type,
                    "subject":   exam_subj,
                    "dept":      exam_dept,
                    "time":      exam_time,
                    "date":      exam_date,
                })
        if clashes:
            conflicts[ev.event_id] = clashes
    return conflicts


# ---------------------------------------------------------------------------
# Student-facing chatbot handlers (override CLI handlers)
# ---------------------------------------------------------------------------
# Known departments — used for entity extraction (O(1) set lookup)
_DEPT_ALIASES: dict = {
    # Keys: anything a student might type → canonical dept code
    "cs": "CS", "cse": "CS", "computer": "CS", "computers": "CS",
    "it": "IT", "information": "IT",
    "ece": "ECE", "electronics": "ECE", "electronic": "ECE",
    "eee": "EEE", "electrical": "EEE", "electricals": "EEE",
    "me": "ME",  "mechanical": "ME", "mech": "ME",
    "all": "ALL", "every": "ALL", "everyone": "ALL",
}

# Hostel sharing tier aliases
_SHARING_ALIASES: dict = {
    "3": "triple", "three": "triple", "triple": "triple", "3-sharing": "triple", "3sharing": "triple",
    "4": "quad",   "four":  "quad",  "quad":   "quad",   "4-sharing": "quad",   "4sharing": "quad",
    "2": "twin",   "two":   "twin",  "twin":   "twin",   "double":    "twin",   "2-sharing": "twin",
}


def _extract_entities(query: str) -> dict:
    """
    Scans the raw query for department, branch, and hostel tier mentions.

    Python concepts:
    - Single-pass tokenisation using str.translate + str.split
    - Dict.get() for O(1) alias resolution (no if/elif chains)
    - Returns a plain dict — callers destructure what they need
    """
    tokens = query.lower().translate(str.maketrans("", "", "?.,!;:\"'")).split()
    dept:    str | None = None
    sharing: str | None = None

    for tok in tokens:
        if tok in _DEPT_ALIASES and dept is None:
            dept = _DEPT_ALIASES[tok]
        if tok in _SHARING_ALIASES and sharing is None:
            sharing = _SHARING_ALIASES[tok]

    return {"dept": dept, "sharing": sharing}


def _web_show_events(dept: str | None = None) -> str:
    """
    Returns formatted events, optionally filtered by department.

    Python concepts used:
    - defaultdict(list) groups events by date string
    - sorted() with a lambda tuple key: (date, start_time)
    - Conditional list filtering with a generator expression
    - set comprehension to deduplicate clash exam-types
    """
    from collections import defaultdict
    conflicts = _build_conflicts(events, schedule_df)

    # Filter events — generator expression (lazy, memory-efficient)
    filtered = [
        ev for ev in sorted(events, key=lambda e: (e.date, e.start_time))
        if dept is None or dept == "ALL"
           or ev.department.upper() == dept
           or ev.department.upper() == "ALL"
    ]

    if not filtered:
        return f"No events found for the **{dept}** department."

    header = f"UPCOMING EVENTS" if dept is None else f"{dept} EVENTS"
    lines  = [header, ""]

    by_date: dict = defaultdict(list)
    for ev in filtered:
        by_date[ev.date.strftime("%d %b %Y")].append(ev)

    for date_str, day_events in by_date.items():
        lines.append(f"--- {date_str} ---")
        for ev in day_events:
            lines.append(f"• **{ev.name}**")
            lines.append(f"  {ev.start_time}–{ev.end_time}  ·  {ev.location}  [{ev.department}]")
            ev_clashes = conflicts.get(ev.event_id, [])
            if ev_clashes:
                same_day: set = {c["exam_type"] for c in ev_clashes if c["kind"] == "same_day"}
                next_day: set = {c["exam_type"] for c in ev_clashes if c["kind"] == "day_before"}
                if same_day:
                    lines.append(f"  ⚠ Exam clash: {', '.join(sorted(same_day))} on the same day")
                if next_day:
                    lines.append(f"  ℹ Heads up: {', '.join(sorted(next_day))} exam the next day")
        lines.append("")

    return "\n".join(lines)


def _web_show_fees(branch: str | None = None, hostel_tier: str | None = None) -> str:
    """
    Returns fees filtered by branch and/or hostel sharing tier.

    Python concepts:
    - dict.get() for O(1) branch lookup
    - Conditional branching avoids sending irrelevant data
    - f-string formatting with nested expressions
    """
    lines = []

    # ── Branch tuition ──────────────────────────────────────────────────────
    if hostel_tier is None:          # don't show tuition when only hostel was asked
        if branch and branch in BRANCH_TUITION:
            bt    = BRANCH_TUITION[branch]
            total = compute_semester_total(branch)
            lines += [
                f"{branch} TUITION FEES",
                "",
                f"• **Semester Fee**  ·  {currency_filter(bt['semester_fee'])}  ·  Per semester",
                f"• **Lab Fee**       ·  {currency_filter(bt['lab_fee'])}  ·  Per semester",
                f"• **Exam Fee**      ·  {currency_filter(bt['exam_fee'])}  ·  Per theory exam",
                "",
                f"  Total per semester: **{currency_filter(total)}**",
                f"  {bt['note']}",
            ]
        elif branch is None and hostel_tier is None:
            # Full tuition overview
            lines += ["TUITION FEES BY BRANCH", ""]
            for code, bt in BRANCH_TUITION.items():
                total = compute_semester_total(code)
                lines.append(
                    f"• **{code}** — Semester {currency_filter(bt['semester_fee'])}  "
                    f"+ Lab {currency_filter(bt['lab_fee'])}  "
                    f"= **{currency_filter(total)}/sem**"
                )

    # ── Hostel tier ─────────────────────────────────────────────────────────
    if hostel_tier:
        # Map incoming tier name to table column key
        tier_key = {"triple": "triple", "quad": "quad", "twin": None}.get(hostel_tier)
        if tier_key is None:
            lines += [
                "HOSTEL FEES",
                "",
                "Sorry, we only have **3-sharing** and **4-sharing** rooms available.",
                f"• 3-sharing: {currency_filter(HOSTEL_SEMESTER_TOTAL['triple'])} /sem",
                f"• 4-sharing: {currency_filter(HOSTEL_SEMESTER_TOTAL['quad'])} /sem",
            ]
        else:
            tier_label = "3-Sharing" if tier_key == "triple" else "4-Sharing"
            lines += [f"HOSTEL FEES — {tier_label} Room", ""]
            for row in HOSTEL_TIERS:
                lines.append(
                    f"• **{row['name']}**  ·  {currency_filter(row[tier_key])}  ·  {row['frequency']}"
                )
                lines.append(f"  {row['note']}")
            lines += [
                "",
                f"  Per-semester total (excl. deposit): "
                f"**{currency_filter(HOSTEL_SEMESTER_TOTAL[tier_key])}**",
            ]

    # ── Common fees (always shown unless only hostel was asked) ──────────────
    if hostel_tier is None:
        lines += ["", "COMMON FEES (ALL BRANCHES)", ""]
        for item in COMMON_FEES:
            lines.append(f"• **{item['name']}**  ·  {currency_filter(item['amount'])}  ·  {item['frequency']}")

    lines += ["", f"  {PAYMENT_NOTE}"]
    return "\n".join(lines)


def _web_show_schedule() -> str:
    """
    Chat handler — outputs exam schedule grouped by ExamType,
    then sorted by Department within each group.

    Python concepts:
    - sorted() with multi-key lambda (exam_type_order, dept, date)
    - defaultdict(list) to group rows by ExamType
    - dict comprehension to build exam_type order-index
    """
    from collections import defaultdict

    TYPE_ORDER = {t: i for i, t in enumerate(["CIA1", "CIA2", "CIA3", "Lab", "Semester"])}

    # Sort: exam type order first, then department alpha, then date
    df_sorted = schedule_df.sort_values(
        ["ExamType", "Department", "Date"],
        key=lambda col: col.map(TYPE_ORDER) if col.name == "ExamType" else col
    )

    # Group by ExamType using defaultdict
    by_type: dict = defaultdict(list)
    for row in df_sorted.itertuples(index=False):
        by_type[row.ExamType].append(row)

    lines = ["EXAM SCHEDULE", ""]
    for etype in ["CIA1", "CIA2", "CIA3", "Lab", "Semester"]:
        if etype not in by_type:
            continue
        lines.append(f"--- {etype} ---")
        current_dept = None
        for row in by_type[etype]:
            if row.Department != current_dept:
                current_dept = row.Department
                lines.append(f"• **{row.Department}**")
            lines.append(
                f"  {row.Date.strftime('%d %b')}  {row.StartTime}–{row.EndTime}  "
                f"{row.Subject}  [{row.Room}]"
            )
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Build bot with overridden student-facing handlers
# ---------------------------------------------------------------------------
_handlers = build_handlers(students, events, finance_df, schedule_df)
_handlers["events"]   = _web_show_events
_handlers["finance"]  = _web_show_fees
_handlers["schedule"] = _web_show_schedule
bot = Chatbot(_handlers)


# ---------------------------------------------------------------------------
# Chat response parser — strips any leftover file-path lines
# ---------------------------------------------------------------------------
_IMAGE_FILES = ["event_dashboard.png"]


def _parse_response(raw: str):
    ts     = int(time.time())
    images = [f"/output/{f}?t={ts}" for f in _IMAGE_FILES if f in raw]
    map_url = f"/output/campus_map.html?t={ts}" if "campus_map.html" in raw else None
    text = re.sub(r"={20,}", "", raw)
    text = re.sub(
        r"\n[ \t]*(Charts saved|Visual dashboard saved"
        r"|Campus map.*saved|Interactive map saved"
        r"|Open it in your browser)[^\n]*",
        "",
        text,
    )
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, images, map_url


# ---------------------------------------------------------------------------
# Page routes  (student-facing only)
# ---------------------------------------------------------------------------
@app.route("/")
def dashboard():
    import datetime as _dt
    today = _dt.date.today()
    upcoming = sorted(
        [e for e in events if e.date.date() >= today],
        key=lambda e: e.date
    )[:3]
    # Next exam across all departments
    future_exams = schedule_df[schedule_df["Date"].dt.date >= today].sort_values("Date")
    next_exam = future_exams.iloc[0] if not future_exams.empty else None
    return render_template(
        "dashboard.html",
        total_events   = len(events),
        upcoming_events = upcoming,
        next_exam      = next_exam,
        conflicts      = _build_conflicts(events, schedule_df),
    )


@app.route("/events")
def events_page():
    generate_campus_map(events)
    ts = int(time.time())
    return render_template(
        "events.html",
        events    = sorted(events, key=lambda e: (e.date, e.start_time)),
        map_url   = f"/output/campus_map.html?t={ts}",
        conflicts = _build_conflicts(events, schedule_df),
    )


@app.route("/fees")
def fees_page():
    # Pass all branch data and hostel tiers — template handles client-side switching
    return render_template(
        "fees.html",
        branch_tuition        = BRANCH_TUITION,
        common_fees           = COMMON_FEES,
        hostel_tiers          = HOSTEL_TIERS,
        hostel_semester_total = HOSTEL_SEMESTER_TOTAL,
        payment_note          = PAYMENT_NOTE,
    )


@app.route("/schedule")
def schedule_page():
    # Build row list — Python list‑comprehension over itertuples() is faster than iterrows()
    rows = [
        {
            "date":      row.Date,
            "start":     row.StartTime,
            "end":       row.EndTime,
            "dept":      row.Department,
            "subject":   row.Subject,
            "room":      row.Room,
            "exam_type": row.ExamType,
        }
        for row in schedule_df.sort_values(["Date", "Department"]).itertuples(index=False)
    ]
    # Sorted unique departments for the filter dropdown
    dept_list: list = sorted(schedule_df["Department"].unique().tolist())
    return render_template("schedule.html", rows=rows, dept_list=dept_list)


@app.route("/chat")
def chat():
    return render_template("chat.html")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    Smart chat dispatcher  —  Entity-first routing.

    Pipeline:
    1. _extract_entities()  — O(1) dict lookups per token (dept, sharing tier)
    2. Presence checks for event/fee keyword sets  — O(k) per query
    3. classify_intent()   — Levenshtein fallback only when entities ambiguous
    4. Filtered handler call with extracted entities

    Entity-first is critical: 'what are the upcoming cs events' contains 'what'
    which scores +2 for the 'help' PRIORITY intent, beating 'events' in a tie.
    We must detect (dept + event_word) BEFORE falling through to classify_intent.
    """
    from src.chatbot import classify_intent

    data  = request.get_json(silent=True) or {}
    query = data.get("message", "").strip()
    if not query:
        return jsonify({"text": "Please type something.", "images": [], "map": None,
                        "chips": []})

    q_lower  = query.lower()
    entities = _extract_entities(query)
    dept     = entities["dept"]
    sharing  = entities["sharing"]

    # ── Word-set presence checks  (O(k) where k = number of sentinel words) ──
    EVENT_WORDS: frozenset = frozenset({
        "event", "events", "fest", "workshop", "hackathon", "contest", "fair",
        "cultural", "startup", "robotics", "career", "coding", "presentation",
        "upcoming", "happening", "show", "schedule", "activity"
    })
    FEE_WORDS: frozenset = frozenset({
        "fee", "fees", "cost", "hostel", "tuition", "payment", "money",
        "expense", "charges", "sharing", "room", "accommodation"
    })
    q_tokens: set = set(q_lower.translate(str.maketrans("", "", "?.,!;:\"'")).split())

    has_event_word  = bool(q_tokens & EVENT_WORDS)
    has_fee_word    = bool(q_tokens & FEE_WORDS)
    is_hostel       = any(w in q_lower for w in ("hostel", "room", "sharing", "accommodation", "mess"))
    is_tuition      = any(w in q_lower for w in ("tuition", "semester fee", "lab fee", "academic fee"))

    # ── Unique departments from events data ─────────────────────────────────
    ev_depts: list = sorted({ev.department for ev in events if ev.department != "ALL"})

    # ====================================================================
    # ENTITY-FIRST ROUTING
    # Priority: explicit entity signals beat intent classification.
    # ====================================================================

    # ── 1. dept + event-word  → EVENTS (e.g. "what are the upcoming cs events")
    if dept and has_event_word and not has_fee_word:
        raw  = _web_show_events(dept=dept)
        text, images, map_url = _parse_response(raw)
        follow = [] if dept == "ALL" else ["all events", "show schedule"]
        return jsonify({"text": text, "images": images, "map": map_url, "chips": follow})

    # ── 2. sharing tier  → HOSTEL FEES (e.g. "3 sharing fees", "4-sharing costs")
    if sharing:
        raw  = _web_show_fees(hostel_tier=sharing)
        text, images, map_url = _parse_response(raw)
        return jsonify({"text": text, "images": images, "map": map_url,
                        "chips": ["3-sharing fees", "4-sharing fees", "tuition fees", "all fees"]})

    # ── 3. dept + fee-word  → BRANCH FEES (e.g. "CS fees", "what are IT fees")
    if dept and has_fee_word and not is_hostel:
        branch = dept if dept != "ALL" else None
        raw    = _web_show_fees(branch=branch)
        text, images, map_url = _parse_response(raw)
        return jsonify({"text": text, "images": images, "map": map_url,
                        "chips": ["all fees", "hostel fees", "3-sharing fees", "4-sharing fees"]})

    # ── 4. hostel-word alone  → ask which tier
    if is_hostel and not sharing:
        return jsonify({
            "text": "Which room type would you like to know about?",
            "images": [], "map": None,
            "chips": ["3-sharing hostel fees", "4-sharing hostel fees", "all hostel fees"],
        })

    # ====================================================================
    # INTENT CLASSIFICATION FALLBACK
    # ====================================================================
    intent = classify_intent(query)

    if intent == "events":
        if dept is None:
            dept_chips = [f"{d} events" for d in ev_depts] + ["all events"]
            return jsonify({
                "text": "Which department's events would you like to see?",
                "images": [], "map": None, "chips": dept_chips,
            })
        raw  = _web_show_events(dept=dept)
        text, images, map_url = _parse_response(raw)
        follow = [] if dept == "ALL" else ["all events", "show schedule"]
        return jsonify({"text": text, "images": images, "map": map_url, "chips": follow})

    if intent == "finance":
        if not dept and not sharing and not is_hostel and not is_tuition:
            branch_chips = [f"{c} fees" for c in BRANCH_TUITION.keys()]
            return jsonify({
                "text": "What would you like to know about fees?",
                "images": [], "map": None,
                "chips": branch_chips + ["hostel fees", "all fees"],
            })
        raw = _web_show_fees()
        text, images, map_url = _parse_response(raw)
        return jsonify({"text": text, "images": images, "map": map_url, "chips": []})

    if intent == "schedule":
        raw = _web_show_schedule()
        text, images, map_url = _parse_response(raw)
        dept_chips = [f"{d} schedule" for d in sorted(schedule_df["Department"].unique())]
        return jsonify({"text": text, "images": images, "map": map_url,
                        "chips": dept_chips + ["show events", "fees"]})

    # ── Other intents (map, optimize, students, help, unknown) ───────────────
    raw = bot.handle(query)
    if raw == "__QUIT__":
        return jsonify({"text": "Refresh the page to start a new session.",
                        "images": [], "map": None, "chips": []})
    text, images, map_url = _parse_response(raw)
    return jsonify({"text": text, "images": images, "map": map_url, "chips": []})


@app.route("/output/<filename>")
def serve_output(filename):
    return send_from_directory(OUTPUT_DIR, filename)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)
