"""
main.py
-------
CLI entry point for CampusCopilot.

RESPONSIBILITIES (thin layer only):
  1. Load data via data_loader.
  2. Wire up handlers that call analysis / visualization / algorithms.
  3. Run the chatbot loop.

This file should stay SHORT. Business logic lives in the dedicated modules;
main.py is just the conductor of the orchestra.

Run:
    python -m src.main          (from project root)
    # or
    python main.py              (from project root, using the thin shim below)
"""

from __future__ import annotations

import sys
from typing import List

from .algorithms import (
    binary_search_event_by_date,
    optimize_event_budget,
    select_max_events,
)
from .analysis import (
    department_student_count,
    department_utilization,
    fee_defaulters,
    fees_distribution,
    monthly_budget_trend,
    total_fees_collected,
    total_fees_pending,
)
from .campus_map import generate_campus_map
from .chatbot import Chatbot
from .data_loader import (
    build_departments,
    load_events,
    load_finance,
    load_schedule,
    load_students,
)
from .models import Event, Student
from .visualization import (
    plot_department_expenses,
    plot_event_dashboard,
    plot_fees_distribution,
    plot_monthly_trend,
)


# =============================================================================
# Small presentation helpers. Kept local because they're only used here.
# =============================================================================
def _banner(title: str) -> str:
    """Pretty divider for CLI output."""
    line = "=" * 60
    return f"\n{line}\n  {title}\n{line}"


def _format_currency(amount: float) -> str:
    """Indian-style comma formatting: 1,00,000 readability bonus."""
    return f"INR {amount:,.0f}"


# =============================================================================
# INTENT HANDLERS
# Each handler is a plain function (no self, no state) that returns a string.
# We use closures (functions-within-a-function) to bind them to the loaded
# data without making every handler take 5 arguments.
# =============================================================================
def build_handlers(
    students: List[Student],
    events: List[Event],
    finance_df,
    schedule_df,
):
    # --------- events ---------
    def show_events() -> str:
        lines = [_banner("UPCOMING EVENTS")]
        # Sort events by date, earliest first.
        for ev in sorted(events, key=lambda e: (e.date, e.start_time)):
            lines.append(
                f"  {ev.date.date()}  {ev.start_time}-{ev.end_time}  "
                f"[{ev.department:>4}]  {ev.name:30s}  @ {ev.location}"
            )
        return "\n".join(lines)

    # --------- finance ---------
    def show_finance() -> str:
        util = department_utilization(finance_df)
        collected = total_fees_collected(students)
        pending   = total_fees_pending(students)

        lines = [_banner("FINANCIAL OVERVIEW")]
        lines.append(f"  Total fees collected : {_format_currency(collected)}")
        lines.append(f"  Total fees pending   : {_format_currency(pending)}")
        lines.append("\n  Department utilization:")
        for _, row in util.iterrows():
            lines.append(
                f"    {row['Department']:>4}  "
                f"Expense={_format_currency(row['TotalExpense'])}  "
                f"Budget={_format_currency(row['TotalBudget'])}  "
                f"[{row['Status']}]  ({row['Utilization%']}%)"
            )

        # Save chart PNGs for the demo.
        p1 = plot_department_expenses(util)
        p2 = plot_monthly_trend(monthly_budget_trend(finance_df))
        p3 = plot_fees_distribution(fees_distribution(students))
        lines.append(f"\n  Charts saved: {p1}, {p2}, {p3}")
        return "\n".join(lines)

    # --------- schedule ---------
    def show_schedule() -> str:
        lines = [_banner("EXAM SCHEDULE")]
        for _, row in schedule_df.sort_values("Date").iterrows():
            lines.append(
                f"  {row['Date'].date()}  {row['StartTime']}-{row['EndTime']}  "
                f"[{row['Department']:>4}]  {row['Subject']:25s}  Room: {row['Room']}"
            )
        return "\n".join(lines)

    # --------- students ---------
    def show_students() -> str:
        counts = department_student_count(students)
        defaulters = fee_defaulters(students)

        lines = [_banner("STUDENT OVERVIEW")]
        lines.append(f"  Total students: {len(students)}")
        lines.append("\n  Students per department:")
        for dept, n in sorted(counts.items()):
            lines.append(f"    {dept:>4}: {n}")

        if defaulters:
            lines.append(f"\n  Fee defaulters ({len(defaulters)}):")
            for s in defaulters:
                lines.append(f"    {s.student_id}  {s.name:20s}  "
                             f"due = {_format_currency(s.fees_due)}")
        else:
            lines.append("\n  No fee defaulters. Great!")
        return "\n".join(lines)

    # --------- map ---------
    def show_map() -> str:
        path = generate_campus_map(events)
        return (f"{_banner('CAMPUS MAP GENERATED')}\n"
                f"  Interactive map saved to: {path}\n"
                f"  Open it in your browser to explore.")

    # --------- optimize: THE DSA SHOWCASE ---------
    def show_optimize() -> str:
        lines = [_banner("ALGORITHMIC RECOMMENDATIONS")]

        # --- Greedy: Activity Selection ---
        lines.append("\n  [Greedy] Max non-overlapping events a student can attend:")
        selected = select_max_events(events)
        for ev in selected:
            lines.append(f"    - {ev.date.date()}  "
                         f"{ev.start_time}-{ev.end_time}  {ev.name}")
        lines.append(f"  Count: {len(selected)} events")

        # --- Knapsack: budget-constrained event funding ---
        sponsor_budget = 100_000
        chosen, reach = optimize_event_budget(events, sponsor_budget)
        lines.append(f"\n  [DP/Knapsack] Best events to fund under budget "
                     f"{_format_currency(sponsor_budget)}:")
        for ev in chosen:
            lines.append(f"    - {ev.name:30s}  "
                         f"cost={_format_currency(ev.cost)}  reach={ev.students_reached}")
        lines.append(f"  Total students reached: {reach}")

        # --- Binary search demo ---
        target = "2026-04-25"
        sorted_events = sorted(events, key=lambda e: e.date)
        idx = binary_search_event_by_date(sorted_events, target)
        if idx != -1:
            lines.append(f"\n  [Binary Search] First event on {target}: "
                         f"{sorted_events[idx].name}")
        else:
            lines.append(f"\n  [Binary Search] No event found on {target}.")

        # Save the combined dashboard PNG.
        chart = plot_event_dashboard(events, selected)
        lines.append(f"\n  Visual dashboard saved: {chart}")

        # Save a map with selected events highlighted.
        selected_ids = {e.event_id for e in selected}
        map_path = generate_campus_map(events, selected_ids)
        lines.append(f"  Campus map (highlighted) saved: {map_path}")

        return "\n".join(lines)

    # --------- help ---------
    def show_help() -> str:
        return (_banner("HELP") +
                "\n  Ask me things like:\n"
                "    'show events'            -> list all events\n"
                "    'what are the fees?'     -> financial overview + charts\n"
                "    'exam schedule'          -> exam timetable\n"
                "    'show students'          -> enrollment + defaulters\n"
                "    'campus map'             -> interactive Folium map\n"
                "    'optimize events'        -> run DSA recommendations\n"
                "    'help'                   -> this menu\n"
                "    'quit'                   -> exit\n"
                "\n  Typos are fine -- fuzzy matching handles them.")

    def do_quit() -> str:
        return "__QUIT__"   # sentinel the loop looks for

    return {
        "events":   show_events,
        "finance":  show_finance,
        "schedule": show_schedule,
        "students": show_students,
        "map":      show_map,
        "optimize": show_optimize,
        "help":     show_help,
        "quit":     do_quit,
    }


# =============================================================================
# THE CLI LOOP
# =============================================================================
def run() -> None:
    print(_banner("CAMPUSCOPILOT - Intelligent University Assistant"))
    print("  Loading data...")

    # Load everything up-front so every query is instant afterwards.
    try:
        students    = load_students()
        events      = load_events()
        finance_df  = load_finance()
        schedule_df = load_schedule()
        _departments = build_departments(finance_df)  # pre-warm the cache
    except FileNotFoundError as exc:
        # Graceful failure with a clear message (vs a Python traceback).
        print(f"\n[ERROR] {exc}")
        sys.exit(1)

    print(f"  Loaded {len(students)} students, {len(events)} events, "
          f"{len(finance_df)} finance rows, {len(schedule_df)} exams.")
    print("  Type 'help' for commands or 'quit' to exit.\n")

    handlers = build_handlers(students, events, finance_df, schedule_df)
    bot = Chatbot(handlers)

    while True:
        try:
            query = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl-D or Ctrl-C -> clean exit instead of an ugly traceback.
            print("\nGoodbye!")
            break

        if not query:
            continue

        response = bot.handle(query)
        if response == "__QUIT__":
            print("Goodbye!")
            break
        print(response)


if __name__ == "__main__":
    run()
