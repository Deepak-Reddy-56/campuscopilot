"""
chatbot.py
----------
Keyword-based chatbot with fuzzy-match fallback.

HOW IT WORKS:
  1. Every user query is lower-cased and split into words.
  2. Each word is checked against a hash-table of known keywords per intent.
     (Hash-table lookup = O(1) average -- faster than scanning lists.)
  3. Any word that misses the hash-table falls through to Levenshtein
     fuzzy matching (algorithms.py) so typos still resolve.
  4. We pick the intent with the highest keyword score.

Why not full NLP (spaCy/NLTK/transformers)?
  - 5-hour hackathon constraint.
  - Judges want something we can FULLY explain in Q&A. A transformer
    black-box costs points on explainability.
  - For a campus-scope vocabulary, keyword + fuzzy is genuinely sufficient
    and shows off DP + hash tables.
"""

from typing import Callable, Dict, List, Set

from .algorithms import find_closest_keyword


# -----------------------------------------------------------------------------
# INTENT REGISTRY
# A dict-of-sets. Intents map to the keywords that should trigger them.
# Using SETS (not lists) -> O(1) "in" checks vs O(n) for lists.
# -----------------------------------------------------------------------------
INTENT_KEYWORDS: Dict[str, Set[str]] = {
    "events":        {"event", "events", "fest", "workshop", "hackathon",
                      "competition", "contest", "programs"},
    "finance":       {"fee", "fees", "expense", "expenses", "budget",
                      "money", "finance", "financial", "cost", "spending"},
    "schedule":      {"schedule", "exam", "exams", "timetable", "class",
                      "classes", "test", "tests"},
    "students":      {"student", "students", "enrolled", "enrollment",
                      "defaulter", "defaulters", "pending"},
    "map":           {"map", "location", "where", "campus", "directions"},
    "optimize":      {"optimize", "optimise", "best", "maximum", "plan",
                      "recommend", "suggest"},
    "help":          {"help", "commands", "menu", "options", "what"},
    "quit":          {"quit", "exit", "bye", "goodbye", "stop", "close"},
}

# Action intents beat noun intents in a tie. When a user types
# "optimize events", both "optimize" and "events" score 2; without this
# priority table the noun wins by dict-insertion-order and the wrong
# handler fires. This list is our explicit, easy-to-explain tiebreaker.
PRIORITY_INTENTS = ("quit", "help", "optimize", "map")


def _tokenize(query: str) -> List[str]:
    """
    Lower-case and split on whitespace. Strips common punctuation.

    str.translate + str.maketrans is the fastest way in pure Python to strip
    multiple characters in one pass (done in C under the hood).
    """
    cleaned = query.lower().translate(str.maketrans("", "", "?.,!;:"))
    return cleaned.split()


def classify_intent(query: str) -> str:
    """
    Decides which intent best matches the user's query.
    Returns the intent name (a key of INTENT_KEYWORDS), or "unknown".

    Scoring:
      +2 per EXACT keyword hit
      +1 per FUZZY match (Levenshtein <= 2) -- fuzzy is worth less than exact.

    Ties: whichever intent was declared first wins (dict insertion order).
    """
    tokens = _tokenize(query)
    if not tokens:
        return "unknown"

    # Precompute a flat keyword list for fuzzy fallback.
    all_keywords = [kw for kws in INTENT_KEYWORDS.values() for kw in kws]

    scores: Dict[str, int] = {intent: 0 for intent in INTENT_KEYWORDS}

    for token in tokens:
        # --- Exact match (hash-table O(1) per intent) ---
        matched_exactly = False
        for intent, kw_set in INTENT_KEYWORDS.items():
            if token in kw_set:
                scores[intent] += 2
                matched_exactly = True

        # --- Fuzzy match (Levenshtein DP) -- only if exact failed ---
        if not matched_exactly:
            closest = find_closest_keyword(token, all_keywords, max_distance=2)
            if closest:
                for intent, kw_set in INTENT_KEYWORDS.items():
                    if closest in kw_set:
                        scores[intent] += 1
                        break   # avoid double-counting across intents

    # Pick the highest-scoring intent. If everything's 0, we don't know.
    # Tiebreaker: a priority intent (action verb) beats a noun intent when
    # both share the top score. This keeps "optimize events" -> optimize,
    # not -> events.
    max_score = max(scores.values())
    if max_score == 0:
        return "unknown"

    for intent in PRIORITY_INTENTS:
        if scores[intent] == max_score:
            return intent

    best_intent = max(scores, key=scores.get)
    return best_intent


class Chatbot:
    """
    Stateful chatbot. Instantiate once, then call .handle(query) repeatedly.

    Uses the COMMAND PATTERN: intents map to handler callables, stored in a
    dict. Adding a new intent = add one line to INTENT_KEYWORDS plus one line
    to self.handlers. No if/elif ladder to grow -> clean and extensible.
    """

    def __init__(self, handlers: Dict[str, Callable[[], str]]) -> None:
        """
        Parameters
        ----------
        handlers : mapping of intent name -> function returning a text response.
                   The function takes no args -- it closes over whatever data
                   it needs (see main.py for how we wire it up).
        """
        self.handlers = handlers

    def handle(self, query: str) -> str:
        intent = classify_intent(query)
        # dict.get() with a default avoids KeyError for "unknown".
        handler = self.handlers.get(intent, self._unknown)
        return handler()

    @staticmethod
    def _unknown() -> str:
        return (
            "Sorry, I didn't catch that. Try asking about:\n"
            "  events | fees | schedule | students | map | optimize | help"
        )
