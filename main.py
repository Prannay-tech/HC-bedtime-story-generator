"""
Hippocratic AI Coding Assignment — Children's Story Generator
LangGraph multi-agent pipeline: Classifier → Planner → Storyteller → Judge → Refiner

Before submitting the assignment, describe here in a few sentences what you would have built next
if you spent 2 more hours on this project:

I would have added streaming output so the story renders word-by-word in the terminal — far more
engaging for a bedtime story demo. I'd also add a voice synthesis step (gTTS or ElevenLabs) so
the story is read aloud, which is directly on-brand for Hippocratic AI's voice-first healthcare
agent vision. Finally, I'd wire in LangSmith tracing so every graph execution is logged and
observable — essential for debugging and iterating on prompt quality at scale.
"""

import os
import sys
import textwrap

from utils import StoryConfig
from graph import run_pipeline
from agents import NarrativeRefinePass


# ── Display helpers ───────────────────────────────────────────────────────────

WIDTH = 72

def divider(char: str = "─") -> None:
    print(char * WIDTH)

def print_header() -> None:
    divider("═")
    print("  ✦  Bedtime Story Generator  ✦".center(WIDTH))
    print("  Powered by a LangGraph multi-agent pipeline".center(WIDTH))
    divider("═")
    print()

def print_story(story: str) -> None:
    divider()
    print()
    for paragraph in story.split("\n"):
        if paragraph.strip():
            print(textwrap.fill(paragraph.strip(), width=WIDTH))
            print()
    divider()

def print_scorecard(state: dict) -> None:
    if not state.get("iterations"):
        return

    last = state["iterations"][-1]["evaluation"]
    scores = last.get("scores", {})
    overall = last.get("overall", 0)
    fk = last.get("reading_level_grade", "n/a")
    n_iters = len(state["iterations"])
    total_calls = state.get("total_calls", 0)
    dim_failures = last.get("dimension_failures", {})

    print()
    print("  Pipeline summary".center(WIDTH))
    divider()
    print(f"  Iterations run     : {n_iters}")
    print(f"  Total API calls    : {total_calls}")
    print(f"  Final overall score: {overall:.2f} / 10")
    print(f"  Reading level (FK) : Grade {fk}  (informational)")
    print()

    label_map = {
        "content_safety":           "Content safety      ",
        "vocabulary_accessibility": "Vocab accessibility ",
        "coherence":                "Coherence           ",
        "narrative_arc":            "Narrative arc       ",
        "engagement":               "Engagement          ",
    }
    for key, label in label_map.items():
        score = scores.get(key, 0)
        bar = "█" * int(score) + "░" * (10 - int(score))
        print(f"  {label}: {bar} {score:.1f}")

    if dim_failures:
        print(f"\n  Failed checks      : {', '.join(dim_failures.keys())}")
    strongest = last.get("strongest_element", "")
    if strongest:
        print(f"  Strongest element  : {strongest}")
    divider()
    print()


# ── User feedback loop ────────────────────────────────────────────────────────

def ask_for_feedback(story: str, state: dict, config: StoryConfig) -> str:
    """Let the user request targeted changes after the story is delivered."""
    print("Would you like any changes to the story?")
    print("  Examples: 'make it funnier', 'shorter ending', 'add a dragon', or press Enter to finish.")
    print()

    refiner = NarrativeRefinePass()

    while True:
        feedback = input("Your feedback (or Enter to finish): ").strip()
        if not feedback:
            break

        print("\nApplying your feedback...\n")
        story = refiner.run(
            story,
            f"User requested: {feedback}",
            [f"Apply this change: {feedback}"],
            config,
        )
        print_story(story)

    return story


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is not set.")
        print("Run: export OPENAI_API_KEY=your-key-here")
        sys.exit(1)

    config = StoryConfig()

    print_header()

    user_input = input("What kind of story do you want to hear?\n> ").strip()
    if not user_input:
        print("No request provided. Exiting.")
        sys.exit(0)

    print()
    print("Generating your story — this may take a moment...\n")

    state = run_pipeline(user_input, config)

    title = state.get("plan", {}).get("title", "Your Story")
    print(f"\n{('  ' + title).center(WIDTH)}")
    print()

    print_story(state["final_story"])
    print_scorecard(state)
    ask_for_feedback(state["final_story"], state, config)

    print("Sweet dreams! 🌙")


if __name__ == "__main__":
    main()
