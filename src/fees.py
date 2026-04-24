"""
fees.py
-------
Student-facing fee structure for CampusCopilot.

Design rationale (Python concepts used):
- BRANCH_TUITION uses a dict-of-dicts — O(1) lookup by branch key.
- HOSTEL_TIERS is a list of dicts so Jinja can iterate and compare columns.
- compute_semester_total() demonstrates a generator expression + sum() — functional style.
All amounts in INR.
"""

from __future__ import annotations
from typing import Dict, List


# ---------------------------------------------------------------------------
# Common one-time + annual fees (same for all branches)
# ---------------------------------------------------------------------------
COMMON_FEES: List[Dict] = [
    {
        "name":      "Registration Fee",
        "amount":    2000,
        "frequency": "One-time",
        "note":      "Non-refundable. Paid once at admission.",
        "badge":     "one-time",
    },
    {
        "name":      "Library Fee",
        "amount":    1500,
        "frequency": "Per year",
        "note":      "Full access to library, e-resources and reading rooms.",
        "badge":     "annual",
    },
    {
        "name":      "Student Activity Fee",
        "amount":    1000,
        "frequency": "Per year",
        "note":      "Funds clubs, fests, and student-organised events.",
        "badge":     "annual",
    },
]

# ---------------------------------------------------------------------------
# Branch-specific tuition (per semester)
# Key  → shown in UI dropdown.  Uses dict comprehension internally.
# ---------------------------------------------------------------------------
BRANCH_TUITION: Dict[str, Dict] = {
    "CS": {
        "label":        "Computer Science & Engineering",
        "color":        "#6366f1",   # indigo
        "bg":           "#ede9fe",
        "semester_fee": 52000,
        "lab_fee":      4500,
        "exam_fee":     500,
        "note":         "Includes access to high-performance computing labs and software licences.",
    },
    "IT": {
        "label":        "Information Technology",
        "color":        "#0ea5e9",   # sky
        "bg":           "#e0f2fe",
        "semester_fee": 50000,
        "lab_fee":      4000,
        "exam_fee":     500,
        "note":         "Covers networking infrastructure, cloud lab credits, and IT studio access.",
    },
    "ECE": {
        "label":        "Electronics & Communication Engineering",
        "color":        "#8b5cf6",   # violet
        "bg":           "#f3e8ff",
        "semester_fee": 48000,
        "lab_fee":      5000,
        "exam_fee":     500,
        "note":         "Includes hardware lab consumables, signal processing equipment and PCB workshop.",
    },
    "ME": {
        "label":        "Mechanical Engineering",
        "color":        "#f59e0b",   # amber
        "bg":           "#fef3c7",
        "semester_fee": 46000,
        "lab_fee":      5500,
        "exam_fee":     500,
        "note":         "Covers workshop usage, CNC / 3D printing lab, and material testing equipment.",
    },
    "EEE": {
        "label":        "Electrical & Electronics Engineering",
        "color":        "#10b981",   # emerald
        "bg":           "#d1fae5",
        "semester_fee": 47000,
        "lab_fee":      5000,
        "exam_fee":     500,
        "note":         "Includes power systems lab, PLC programming setups, and simulation software.",
    },
}


def compute_semester_total(branch_key: str) -> int:
    """
    Returns total per-semester academic cost for a branch.
    Uses a generator expression — sums only semester-frequency items.
    """
    bt = BRANCH_TUITION[branch_key]
    return bt["semester_fee"] + bt["lab_fee"] + bt["exam_fee"]


# ---------------------------------------------------------------------------
# Hostel fee tiers (3-sharing vs 4-sharing)
# Stored as a list-of-dicts so the template can iterate rows directly.
# ---------------------------------------------------------------------------
HOSTEL_TIERS: List[Dict] = [
    {
        "name":      "Security Deposit",
        "frequency": "One-time (refundable)",
        "badge":     "one-time",
        "note":      "Fully refunded at checkout with no dues or damages.",
        "triple":    10000,   # 3-sharing
        "quad":      10000,   # 4-sharing (same deposit)
    },
    {
        "name":      "Accommodation Fee",
        "frequency": "Per semester",
        "badge":     "semester",
        "note":      "Room charges — triple sharing is more spacious.",
        "triple":    28000,
        "quad":      22000,
    },
    {
        "name":      "Maintenance Fee",
        "frequency": "Per semester",
        "badge":     "semester",
        "note":      "Upkeep of common areas, water, and electricity.",
        "triple":    2500,
        "quad":      2000,
    },
    {
        "name":      "Mess / Dining Fee",
        "frequency": "Per semester",
        "badge":     "semester",
        "note":      "Three meals a day; veg and non-veg options available.",
        "triple":    13000,
        "quad":      12000,
    },
]

# Compute per-semester totals (excluding one-time) — generator expression
HOSTEL_SEMESTER_TOTAL: Dict[str, int] = {
    tier: sum(r[tier] for r in HOSTEL_TIERS if r["badge"] == "semester")
    for tier in ("triple", "quad")
}

# ---------------------------------------------------------------------------
PAYMENT_NOTE = (
    "Fee payments are accepted at the Finance Office (Admin Block, Room 102) "
    "or via the online student portal. Bring your student ID."
)
