"""
LangGraph pipeline for the children's story generator.

Graph structure:
    classify → plan → draft → [expand?] → judge → [refine?] → [expand?] → judge (loop)
                                                             → END

Each node is a pure function: receives StoryState, returns a partial state update.
Conditional edges handle routing — no manual if/else loops in business logic.
"""

import logging
import textstat

from langgraph.graph import StateGraph, END

from state import StoryState
from utils import StoryConfig
from agents import (
    ClassifierAgent, PlannerAgent, StorytellerAgent,
    ExpandPass, NarrativeRefinePass, JudgeAgent,
)
from prompts import JUDGE_MIN_SCORES
from observability import get_run_config, enrich_run_metadata, log_run_summary

logger = logging.getLogger("story_pipeline")

# ── Shared agent instances (stateless — safe to reuse across nodes) ───────────
_classifier = ClassifierAgent()
_planner = PlannerAgent()
_storyteller = StorytellerAgent()
_expand = ExpandPass()
_narrative = NarrativeRefinePass()
_judge = JudgeAgent()


# ── Node functions ────────────────────────────────────────────────────────────
# Each function receives the full state and returns ONLY the keys it changes.

def classify_node(state: StoryState) -> dict:
    """Classify the request into genre, tone, themes, and target age."""
    cfg = state["config"]
    result = _classifier.run(state["request"], cfg)
    return {
        "classification": result,
        "total_calls": 1,
    }


def plan_node(state: StoryState) -> dict:
    """Build a structured 5-beat story plan from the request and classification."""
    cfg = state["config"]
    plan = _planner.run(state["request"], state["classification"], cfg)
    plan["estimated_age_target"] = state["classification"].get("estimated_age_target", 7)
    return {
        "plan": plan,
        "total_calls": 1,
    }


def draft_node(state: StoryState) -> dict:
    """Write the initial story draft. Self-check for word count and vocab is in the prompt."""
    cfg = state["config"]
    genre = state["classification"].get("genre", "adventure")
    story = _storyteller.run(state["plan"], genre, cfg)
    return {
        "story": story,
        "total_calls": 1,
        "iteration_count": 0,
    }


def expand_node(state: StoryState) -> dict:
    """Expand the story if it is below the minimum word count."""
    cfg = state["config"]
    story = _expand.run(state["story"], cfg)
    return {
        "story": story,
        "total_calls": 1,
    }


def judge_node(state: StoryState) -> dict:
    """Score the story on all 5 quality dimensions and check each against its minimum."""
    cfg = state["config"]
    evaluation = _judge.run(state["story"], state["plan"], cfg)
    word_count = len(state["story"].split())

    iteration_entry = {
        "iteration": state.get("iteration_count", 0) + 1,
        "story": state["story"],
        "evaluation": evaluation,
        "word_count": word_count,
    }

    return {
        "evaluation": evaluation,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "iterations": [iteration_entry],
        "total_calls": 1,
    }


def refine_node(state: StoryState) -> dict:
    """Refine the story based on judge critique and failing dimension gates."""
    cfg = state["config"]
    evaluation = state["evaluation"]
    word_count = len(state["story"].split())

    # Build targeted fix list — failing dimensions first, then judge's own fixes
    fixes = []
    for dim, score in evaluation.get("dimension_failures", {}).items():
        fixes.append(
            f"FAILING CHECK '{dim}' (score {score:.1f}, minimum {JUDGE_MIN_SCORES[dim]:.0f}): fix this first."
        )
    if word_count < cfg.min_words:
        fixes.append(
            f"Story is only {word_count} words. Expand to at least {cfg.min_words} words."
        )
    fixes.extend(evaluation.get("specific_fixes", []))

    story = _narrative.run(state["story"], evaluation.get("critique", ""), fixes, cfg)
    return {
        "story": story,
        "total_calls": 1,
    }


def finalize_node(state: StoryState) -> dict:
    """Mark the story as final. Terminal node before END."""
    return {"final_story": state["story"]}


# ── Routing functions (conditional edges) ─────────────────────────────────────

def route_after_draft(state: StoryState) -> str:
    """After drafting: expand if too short, otherwise go straight to judge."""
    if len(state["story"].split()) < state["config"].min_words:
        return "expand"
    return "judge"


def route_after_judge(state: StoryState) -> str:
    """
    After judging: finalize if all gates pass, refine if we have iterations left,
    or finalize anyway if we've hit the max.
    """
    cfg = state["config"]
    evaluation = state["evaluation"]
    word_count = len(state["story"].split())

    overall_ok = evaluation.get("overall", 0) >= cfg.judge_threshold
    dims_ok = evaluation.get("all_dimensions_pass", False)
    length_ok = word_count >= cfg.min_words

    if overall_ok and dims_ok and length_ok:
        logger.info("All quality gates passed. Finalizing.")
        return "finalize"

    if state.get("iteration_count", 0) >= cfg.max_iterations:
        logger.info("Max iterations reached. Finalizing with best available story.")
        return "finalize"

    return "refine"


def route_after_refine(state: StoryState) -> str:
    """After refining: expand if the refine pass shortened the story, otherwise re-judge."""
    if len(state["story"].split()) < state["config"].min_words:
        return "expand"
    return "judge"


# ── Graph assembly ─────────────────────────────────────────────────────────────

def build_graph(config: StoryConfig) -> StateGraph:
    """
    Assemble and compile the LangGraph story pipeline.

    The config is injected into state at invocation time so nodes can access it
    without it being a global — making the graph reusable with different configs.
    """
    graph = StateGraph(StoryState)

    # Register nodes
    graph.add_node("classify", classify_node)
    graph.add_node("plan", plan_node)
    graph.add_node("draft", draft_node)
    graph.add_node("expand", expand_node)
    graph.add_node("judge", judge_node)
    graph.add_node("refine", refine_node)
    graph.add_node("finalize", finalize_node)

    # Linear edges
    graph.set_entry_point("classify")
    graph.add_edge("classify", "plan")
    graph.add_edge("plan", "draft")
    graph.add_edge("expand", "judge")       # After any expand, always judge next

    # Conditional edges
    graph.add_conditional_edges(
        "draft",
        route_after_draft,
        {"expand": "expand", "judge": "judge"},
    )
    graph.add_conditional_edges(
        "judge",
        route_after_judge,
        {"finalize": "finalize", "refine": "refine"},
    )
    graph.add_conditional_edges(
        "refine",
        route_after_refine,
        {"expand": "expand", "judge": "judge"},
    )

    graph.add_edge("finalize", END)

    return graph.compile()


def run_pipeline(request: str, config: StoryConfig) -> StoryState:
    """
    Entry point: run the full pipeline for a single story request.
    Returns the final StoryState with all intermediate data preserved.
    """
    app = build_graph(config)

    initial_state: StoryState = {
        "request": request,
        "config": config,
        "classification": {},
        "plan": {},
        "story": "",
        "evaluation": {},
        "iteration_count": 0,
        "iterations": [],
        "total_calls": 0,
        "final_story": "",
    }

    genre = "unknown"
    run_cfg = get_run_config(request, genre)

    result = app.invoke(initial_state, config=run_cfg)

    # Enrich with actual genre from classification after the graph runs
    actual_genre = result.get("classification", {}).get("genre", genre)
    if actual_genre != genre:
        run_cfg["metadata"]["genre"] = actual_genre

    enrich_run_metadata(run_cfg, result)
    log_run_summary(result)
    return result
