"""
Batch test runner — 50 diverse story requests.
Results are saved to test_results.json after each story so progress
is never lost if the run is interrupted.
"""

import os
import sys
import time
import json

from utils import StoryConfig
from graph import run_pipeline

TEST_REQUESTS = [
    # 2 per genre — 16 total, covers all genre-specific prompt paths
    ("animals",    "A story about a lonely penguin who learns to make friends."),
    ("animals",    "A story about a snail who dreams of winning a race."),
    ("adventure",  "A story about a girl named Alice and her best friend Bob, who happens to be a cat."),
    ("adventure",  "A story about a boy who discovers a secret door in his bedroom."),
    ("fantasy",    "A story about a tiny dragon who is afraid of fire."),
    ("fantasy",    "A story about a wizard who keeps accidentally turning things into cheese."),
    ("moral",      "A story that teaches kids why it's important to tell the truth."),
    ("moral",      "A story about a girl who learns that being different is a strength."),
    ("humor",      "A very silly story about a talking sandwich who wants to go to school."),
    ("humor",      "A story about a king who hiccups every time he tries to give a royal speech."),
    ("mystery",    "A story about two brothers who find a mysterious glowing box in their backyard."),
    ("mystery",    "A story about a kid who discovers their shadow is doing things they didn't do."),
    ("science",    "A story about a curious girl who shrinks down to explore the inside of a flower."),
    ("science",    "A story about a girl who invents a machine that translates animal sounds."),
    ("friendship", "A story about a robot and a puppy who become unlikely best friends."),
    ("friendship", "A story about a new kid at school who is too shy to talk to anyone."),
]

assert len(TEST_REQUESTS) == 16, f"Expected 16 tests, got {len(TEST_REQUESTS)}"

WIDTH = 72
RESULTS_FILE = "test_results.json"


def divider(c="─"):
    print(c * WIDTH)


def save_results(results: list):
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)


def run_tests():
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set.")
        sys.exit(1)

    config = StoryConfig()
    results = []

    # Resume from previous run if interrupted
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE) as f:
            results = json.load(f)
        print(f"Resuming from previous run — {len(results)}/{len(TEST_REQUESTS)} already done.\n")

    start_index = len(results)

    for i, (label, request) in enumerate(TEST_REQUESTS[start_index:], start_index + 1):
        divider("═")
        print(f"  Test {i}/{len(TEST_REQUESTS)}: [{label.upper()}]")
        print(f"  {request}")
        divider()

        start = time.time()
        try:
            state = run_pipeline(request, config)
            elapsed = time.time() - start

            last = state["iterations"][-1]["evaluation"] if state.get("iterations") else {}
            scores = last.get("scores", {})
            overall = last.get("overall", 0)
            fk = last.get("reading_level_grade", None)
            iters = len(state.get("iterations", []))
            calls = state.get("total_calls", 0)
            word_count = len(state.get("final_story", "").split())

            dim_failures = last.get("dimension_failures", {})
            all_dims_pass = last.get("all_dimensions_pass", False)
            passed_all = overall >= config.judge_threshold and all_dims_pass and word_count >= config.min_words

            result = {
                "index": i,
                "label": label,
                "request": request,
                "title": state.get("plan", {}).get("title", "—"),
                "overall": overall,
                "fk_grade": fk,
                "iterations": iters,
                "api_calls": calls,
                "words": word_count,
                "elapsed_s": round(elapsed, 1),
                "scores": scores,
                "passed_score": overall >= config.judge_threshold,
                "passed_dims": all_dims_pass,
                "passed_all": passed_all,
                "dimension_failures": dim_failures,
                "critique": last.get("critique", ""),
                "story_snippet": state.get("final_story", "")[:150].replace("\n", " ") + "...",
            }

            print(f"  Title      : {result['title']}")
            print(f"  Score      : {overall:.2f}/10   FK: {fk}   Words: {word_count}")
            print(f"  Iterations : {iters}   API calls: {calls}   Time: {elapsed:.1f}s")
            print(f"  Dim fails  : {list(dim_failures.keys()) if dim_failures else 'none'}")
            status = "PASS ✓" if passed_all else "FAIL ✗"
            print(f"  Status     : {status}")
            print()

        except Exception as e:
            elapsed = time.time() - start
            print(f"  FAILED after {elapsed:.1f}s: {e}")
            result = {
                "index": i,
                "label": label,
                "request": request,
                "title": "ERROR",
                "overall": 0,
                "fk_grade": None,
                "iterations": 0,
                "api_calls": 0,
                "words": 0,
                "elapsed_s": round(elapsed, 1),
                "scores": {},
                "passed_fk": False,
                "passed_score": False,
                "critique": str(e),
                "story_snippet": "",
            }

        results.append(result)
        save_results(results)  # checkpoint after every story

    print_summary(results, config)


def print_summary(results: list, config: StoryConfig):
    divider("═")
    print("  PERFORMANCE SUMMARY  (16 stories)".center(WIDTH))
    divider("═")

    header = f"{'#':>3} {'Genre':<12} {'Score':>6} {'FK':>5} {'Iters':>6} {'Calls':>6} {'Words':>6} {'Time':>6} {'Pass':>5}"
    print(f"  {header}")
    divider()

    passed = 0
    for r in results:
        fk_str = f"{r['fk_grade']:.1f}" if isinstance(r["fk_grade"], (int, float)) else "err"
        ok = r.get("passed_all", r.get("passed_score", False))
        if ok:
            passed += 1
        row = (
            f"{r['index']:>3} {r['label']:<12} {r['overall']:>6.2f} {fk_str:>5} "
            f"{r['iterations']:>6} {r['api_calls']:>6} {r['words']:>6} "
            f"{r['elapsed_s']:>6.1f} {'✓' if ok else '✗':>5}"
        )
        print(f"  {row}")

    divider()
    valid = [r for r in results if r["overall"] > 0]
    if valid:
        avg_score = sum(r["overall"] for r in valid) / len(valid)
        fk_vals   = [r["fk_grade"] for r in valid if isinstance(r["fk_grade"], (int, float))]
        avg_fk    = sum(fk_vals) / len(fk_vals) if fk_vals else 0
        avg_calls = sum(r["api_calls"] for r in valid) / len(valid)
        avg_time  = sum(r["elapsed_s"] for r in valid) / len(valid)
        avg_iters = sum(r["iterations"] for r in valid) / len(valid)
        avg_words = sum(r["words"] for r in valid) / len(valid)

        print(f"  {'AVG':<16} {avg_score:>6.2f} {avg_fk:>5.1f} {avg_iters:>6.1f} {avg_calls:>6.1f} {avg_words:>6.0f} {avg_time:>6.1f}")
        divider()
        print(f"  Pass rate (score + all dimension gates): {passed}/{len(results)} ({100*passed/len(results):.0f}%)")

    divider("═")
    print()

    # Dimension breakdown by genre
    print("  DIMENSION AVERAGES BY GENRE".center(WIDTH))
    divider()
    dims = ["content_safety", "vocabulary_accessibility", "coherence", "narrative_arc", "engagement"]
    genres = sorted(set(r["label"] for r in valid))
    print(f"  {'Genre':<12} " + " ".join(f"{d[:4]:>5}" for d in dims) + f" {'overall':>8}")
    divider()
    for genre in genres:
        group = [r for r in valid if r["label"] == genre]
        row_parts = []
        for d in dims:
            vals = [r["scores"].get(d, 0) for r in group if r["scores"].get(d)]
            avg = sum(vals) / len(vals) if vals else 0
            row_parts.append(f"{avg:>5.1f}")
        avg_overall = sum(r["overall"] for r in group) / len(group)
        print(f"  {genre:<12} " + " ".join(row_parts) + f" {avg_overall:>8.2f}")
    divider("═")
    print(f"\n  Full results saved to: {RESULTS_FILE}\n")


if __name__ == "__main__":
    run_tests()
