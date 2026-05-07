"""
LangSmith observability for the story pipeline.

When LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY are set, every graph
execution is automatically traced in LangSmith with full node-level visibility.

This module adds structured metadata to each run so traces are meaningful:
  - story genre, tone, target age
  - iteration count and final score
  - pass/fail status per quality dimension
  - word count and FK reading level

Usage:
    from observability import get_run_config, log_run_summary
    config = get_run_config(state)
    app.invoke(initial_state, config=config)
"""

import os
import logging
from langchain_core.runnables.config import RunnableConfig

logger = logging.getLogger("story_pipeline")

LANGSMITH_ENABLED = (
    os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true"
    and bool(os.getenv("LANGCHAIN_API_KEY"))
)


def get_run_config(request: str, genre: str = "unknown") -> RunnableConfig:
    """
    Build a RunnableConfig with metadata for this pipeline run.
    LangGraph passes this through every node automatically.
    """
    project = os.getenv("LANGCHAIN_PROJECT", "hippocratic-story-generator")

    config: RunnableConfig = {
        "run_name": f"story-pipeline | {genre} | {request[:40]}",
        "tags": ["story-generator", f"genre:{genre}"],
        "metadata": {
            "request": request,
            "genre": genre,
            "project": project,
        },
    }

    if LANGSMITH_ENABLED:
        logger.info("LangSmith tracing enabled — project: %s", project)
    else:
        logger.info(
            "LangSmith tracing disabled. "
            "Set LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY to enable."
        )

    return config


def enrich_run_metadata(config: RunnableConfig, state: dict) -> None:
    """
    After the pipeline completes, update the run metadata with outcome data.
    Called once at the end of run_pipeline() so the trace has full context.
    """
    if not LANGSMITH_ENABLED:
        return

    try:
        from langsmith import Client

        client = Client()

        iterations = state.get("iterations", [])
        last_eval = iterations[-1]["evaluation"] if iterations else {}
        scores = last_eval.get("scores", {})
        dim_failures = last_eval.get("dimension_failures", {})

        extra_metadata = {
            "final_score": last_eval.get("overall", 0),
            "iterations_run": len(iterations),
            "total_api_calls": state.get("total_calls", 0),
            "word_count": len(state.get("final_story", "").split()),
            "fk_grade": last_eval.get("reading_level_grade"),
            "all_gates_passed": last_eval.get("all_dimensions_pass", False),
            "failing_dimensions": list(dim_failures.keys()),
            **{f"score_{k}": v for k, v in scores.items()},
        }

        run_id = config.get("run_id")
        if run_id:
            client.update_run(run_id, extra=extra_metadata)

    except Exception as e:
        logger.debug("Could not enrich LangSmith run metadata: %s", e)


def log_run_summary(state: dict) -> None:
    """Print a concise observability summary to the terminal regardless of LangSmith."""
    iterations = state.get("iterations", [])
    last_eval = iterations[-1]["evaluation"] if iterations else {}
    dim_failures = last_eval.get("dimension_failures", {})

    logger.info(
        "Run complete — score: %.2f, iterations: %d, calls: %d, words: %d, "
        "FK: %s, dims: %s",
        last_eval.get("overall", 0),
        len(iterations),
        state.get("total_calls", 0),
        len(state.get("final_story", "").split()),
        last_eval.get("reading_level_grade", "n/a"),
        "all pass" if not dim_failures else f"FAIL: {list(dim_failures.keys())}",
    )

    if LANGSMITH_ENABLED:
        project = os.getenv("LANGCHAIN_PROJECT", "hippocratic-story-generator")
        logger.info("Full trace available in LangSmith project: %s", project)
