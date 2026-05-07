"""
Shared state for the LangGraph story pipeline.

StoryState is passed between every node in the graph.
Each node reads what it needs and returns only the keys it updates.
LangGraph merges partial updates automatically.
"""

from typing import TypedDict, Annotated
import operator


class StoryState(TypedDict):
    # ── Inputs ────────────────────────────────────────────────────────────
    request: str                    # Raw user story request

    # ── Stage outputs ─────────────────────────────────────────────────────
    classification: dict            # Classifier output: genre, tone, themes, target age
    plan: dict                      # Planner output: title, characters, 5-beat structure
    story: str                      # Current working story draft

    # ── Judge output ──────────────────────────────────────────────────────
    evaluation: dict                # Full judge result including scores, failures, critique

    # ── Loop control ──────────────────────────────────────────────────────
    iteration_count: int            # How many judge→refine cycles have run

    # ── Accumulated trace (list fields use operator.add for append semantics) ──
    iterations: Annotated[list, operator.add]   # Full history of each iteration

    # ── Bookkeeping ───────────────────────────────────────────────────────
    total_calls: Annotated[int, operator.add]   # Total LLM API calls made
    final_story: str                             # Set once the graph reaches END
