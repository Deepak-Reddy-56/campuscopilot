# CampusCopilot — Intelligent University Assistant

An interactive command-line university assistant that combines pandas analytics,
matplotlib/Folium visualisation, and four classical DSA algorithms behind a
fuzzy-matching chatbot.

Built for a 5-hour hackathon by a team of 5.

---

## Quick Start (VS Code)

1. Open the project folder in VS Code: `File → Open Folder… → campuscopilot/`
2. Open an integrated terminal: `` Ctrl+` `` (backtick)
3. Create & activate a virtual environment:
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # Mac / Linux
   python3 -m venv venv
   source venv/bin/activate
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Run the app:
   ```bash
   python run.py
   ```
6. Try these queries:
   - `help`
   - `show events`
   - `fees`
   - `exam schedule`
   - `show students`
   - `campus map`
   - `optimize events` ← this is the DSA showcase
   - `evnts` (intentional typo — fuzzy matching will still resolve it)
   - `quit`

PNG charts are written to `output/`, and the Folium map opens as
`output/campus_map.html` (double-click it in VS Code's file explorer).

---

## Project Structure

```
campuscopilot/
├── data/                      # CSV input files (source of truth)
│   ├── students.csv
│   ├── finance.csv
│   ├── events.csv
│   └── schedule.csv
│
├── src/                       # All Python source
│   ├── __init__.py
│   ├── models.py              # OOP domain classes (Student, Event, Department)
│   ├── data_loader.py         # CSV → Python objects / DataFrames
│   ├── algorithms.py          # DSA: Levenshtein, Greedy, Knapsack, Binary Search
│   ├── analysis.py            # Pure pandas analytics
│   ├── visualization.py       # matplotlib charts
│   ├── campus_map.py          # Folium interactive map
│   ├── chatbot.py             # Intent classifier + Command-pattern dispatcher
│   └── main.py                # CLI loop, wiring
│
├── output/                    # Generated charts & map (created on first run)
├── run.py                     # Thin launcher (python run.py)
├── requirements.txt
└── README.md
```

---

## Algorithms Used

| # | Algorithm | Paradigm | Where It's Used | Complexity |
|---|-----------|----------|-----------------|------------|
| 1 | Levenshtein Distance | Dynamic Programming | Fuzzy keyword matching for typo-tolerant chatbot | O(m·n) |
| 2 | Activity Selection | Greedy | Max non-overlapping events a student can attend | O(n log n) |
| 3 | Binary Search | Divide & Conquer | Locating events by date in sorted list | O(log n) |
| 4 | Hash-table lookup | Data Structure | O(1) intent-keyword matching in the chatbot | O(1) avg |

---

## Python Concepts Demonstrated

- **OOP**: `@dataclass`, properties, instance methods (`Event.conflicts_with`)
- **Type hints**: on every public function
- **List / dict / generator comprehensions**
- **Decorators**: `@dataclass`, `@property`, `@staticmethod`
- **Error handling**: custom `FileNotFoundError` message, graceful Ctrl-C exit
- **Modules & packages**: relative imports (`from .models import ...`)
- **Design patterns**: Command (intent → handler dict), Single Responsibility
- **Closures**: handlers bind to data without globals
- **File I/O**: CSV read, PNG write, HTML write
- **pandas**: `read_csv`, `groupby`, `agg`, `merge`, vectorised ops
- **NumPy**: `np.where` for vectorised branching
- **matplotlib**: `subplots`, `tight_layout`, non-interactive `Agg` backend
- **Folium**: `Map`, `Marker`, `CircleMarker`, popups