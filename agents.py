import logging
import textstat

from utils import StoryConfig, call_model, parse_json
from prompts import (
    CLASSIFIER_SYSTEM, classifier_user,
    PLANNER_SYSTEM, planner_user,
    storyteller_system, storyteller_user,
    EXPAND_SYSTEM, expand_user,
    NARRATIVE_REFINE_SYSTEM, narrative_refine_user,
    JUDGE_SYSTEM, JUDGE_WEIGHTS, JUDGE_MIN_SCORES, judge_user,
)

logger = logging.getLogger("story_pipeline")


# ── Classifier ────────────────────────────────────────────────────────────────

class ClassifierAgent:
    """Categorizes the story request into structured metadata."""

    def run(self, request: str, config: StoryConfig) -> dict:
        logger.info("Classifying request...")
        messages = [
            {"role": "system", "content": CLASSIFIER_SYSTEM},
            {"role": "user", "content": classifier_user(request)},
        ]
        raw = call_model(
            messages, config,
            temperature=config.classifier_temperature,
            max_tokens=config.max_tokens_classifier,
            json_mode=True,
        )
        result = parse_json(raw, context="classifier")
        logger.info("Classification: genre=%s, tone=%s", result.get("genre"), result.get("tone"))
        return result


# ── Planner ───────────────────────────────────────────────────────────────────

class PlannerAgent:
    """Builds a structured 5-beat story plan from the request and classification."""

    def run(self, request: str, classification: dict, config: StoryConfig) -> dict:
        logger.info("Building story plan...")
        messages = [
            {"role": "system", "content": PLANNER_SYSTEM},
            {"role": "user", "content": planner_user(request, classification)},
        ]
        raw = call_model(
            messages, config,
            temperature=config.planner_temperature,
            max_tokens=config.max_tokens_plan,
            json_mode=True,
        )
        result = parse_json(raw, context="planner")
        logger.info("Plan created: title='%s'", result.get("title", "Untitled"))
        return result


# ── Storyteller ───────────────────────────────────────────────────────────────

class StorytellerAgent:
    """Writes the initial story draft from the plan, with self-check instructions embedded."""

    def run(self, plan: dict, genre: str, config: StoryConfig) -> str:
        logger.info("Writing story draft...")
        messages = [
            {"role": "system", "content": storyteller_system(genre)},
            {"role": "user", "content": storyteller_user(plan, min_words=config.min_words)},
        ]
        story = call_model(
            messages, config,
            temperature=config.storyteller_temperature,
            max_tokens=config.max_tokens_story,
        )
        logger.info("Draft written (%d words, FK %.1f).", len(story.split()), textstat.flesch_kincaid_grade(story))
        return story


# ── Dedicated single-purpose refinement passes ────────────────────────────────

class ExpandPass:
    """Single job: increase word count. Never changes vocabulary or plot."""

    def run(self, story: str, config: StoryConfig) -> str:
        current = len(story.split())
        logger.info("Expand pass: %d → %d words target.", current, config.min_words)
        messages = [
            {"role": "system", "content": EXPAND_SYSTEM},
            {"role": "user", "content": expand_user(story, current, config.min_words)},
        ]
        result = call_model(
            messages, config,
            temperature=0.7,
            max_tokens=config.max_tokens_story,
        )
        logger.info("After expand: %d words.", len(result.split()))
        return result


class SimplifyPass:
    """
    Surgical sentence-level simplification.
    Identifies only sentences above FK grade 5, rewrites just those,
    splices them back in. Word count stays stable.
    """

    def run(self, story: str, fk_grade: float, config: StoryConfig) -> str:
        import re
        logger.info("Surgical simplify pass: FK %.1f → target ≤ 5.0.", fk_grade)

        # Split into sentences, preserving punctuation
        sentence_pattern = re.compile(r'(?<=[.!?])\s+')
        sentences = sentence_pattern.split(story)

        complex_sentences = [
            (i, s) for i, s in enumerate(sentences)
            if len(s.split()) > 3 and textstat.flesch_kincaid_grade(s) > 5.0
        ]

        if not complex_sentences:
            logger.info("No complex sentences found despite high overall FK. Skipping.")
            return story

        logger.info("Found %d complex sentences to simplify.", len(complex_sentences))

        # Build a targeted prompt with only the offending sentences
        numbered = "\n".join(f"{i}: {s}" for i, s in complex_sentences)
        prompt = (
            f"Simplify only these sentences to grade 3-4 reading level.\n"
            f"Rules: replace 3+ syllable words with simpler ones, break long sentences in two, "
            f"use active voice. Keep meaning identical. Return ONLY the simplified sentences "
            f"in the same numbered format.\n\n{numbered}"
        )
        messages = [
            {"role": "system", "content": SIMPLIFY_SYSTEM},
            {"role": "user", "content": prompt},
        ]
        raw = call_model(messages, config, temperature=0.2, max_tokens=800)

        # Parse numbered response and splice back
        result_sentences = list(sentences)
        for line in raw.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            match = re.match(r'^(\d+):\s*(.+)$', line)
            if match:
                idx, simplified = int(match.group(1)), match.group(2).strip()
                if 0 <= idx < len(result_sentences):
                    result_sentences[idx] = simplified

        result = " ".join(result_sentences)
        new_fk = textstat.flesch_kincaid_grade(result)
        logger.info("After surgical simplify: FK %.1f, %d words.", new_fk, len(result.split()))
        return result


class NarrativeRefinePass:
    """Single job: improve story quality based on judge critique. Never touches vocabulary."""

    def run(self, story: str, critique: str, specific_fixes: list, config: StoryConfig) -> str:
        logger.info("Narrative refine pass.")
        messages = [
            {"role": "system", "content": NARRATIVE_REFINE_SYSTEM},
            {"role": "user", "content": narrative_refine_user(story, critique, specific_fixes)},
        ]
        result = call_model(
            messages, config,
            temperature=config.refiner_temperature,
            max_tokens=config.max_tokens_story,
        )
        logger.info("After narrative refine: %d words.", len(result.split()))
        return result


# ── Judge ─────────────────────────────────────────────────────────────────────

class JudgeAgent:
    """
    Scores story on 5 dimensions.
    Each dimension has an independent minimum score gate.
    FK is informational only — vocabulary_accessibility replaces it as the readability gate.
    """

    def run(self, story: str, plan: dict, config: StoryConfig) -> dict:
        logger.info("Judging story...")
        messages = [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": judge_user(story, plan)},
        ]
        raw = call_model(
            messages, config,
            temperature=config.judge_temperature,
            max_tokens=config.max_tokens_judge,
            json_mode=True,
        )
        result = parse_json(raw, context="judge")

        scores = result.get("scores", {})

        # Recalculate weighted overall — never trust model's self-reported value
        if scores:
            result["overall"] = round(
                sum(scores.get(k, 0) * w for k, w in JUDGE_WEIGHTS.items()), 2
            )

        # Check each dimension against its individual minimum
        dimension_failures = {
            dim: scores.get(dim, 0)
            for dim, min_score in JUDGE_MIN_SCORES.items()
            if scores.get(dim, 0) < min_score
        }
        result["dimension_failures"] = dimension_failures
        result["all_dimensions_pass"] = len(dimension_failures) == 0

        # FK is informational only — for display in scorecard
        result["reading_level_grade"] = round(textstat.flesch_kincaid_grade(story), 1)

        logger.info(
            "Judge: overall=%.2f | %s%s",
            result.get("overall", 0),
            " | ".join(f"{k}={v}" for k, v in scores.items()),
            f" | DIMENSION FAILURES: {dimension_failures}" if dimension_failures else " | all dims pass",
        )
        return result


# StoryPipeline removed — replaced by the LangGraph graph in graph.py.
# All agent classes above are imported as graph nodes there.
