"""
Run all 30 story prompts and save results to test_all.json.
Usage:
    export OPENAI_API_KEY=sk-...
    python3 run_test_all.py
"""

import json
import sys
import time

sys.path.insert(0, ".")
from graph import run_pipeline
from utils import StoryConfig

PROMPTS = [
    "A story about a lonely penguin who learns to make friends.",
    "A story about a snail who dreams of winning a race.",
    "A story about a girl named Alice and her best friend Bob, who happens to be a cat.",
    "A story about a boy who discovers a secret door in his bedroom.",
    "A story about a tiny dragon who is afraid of fire.",
    "A story about a wizard who keeps accidentally turning things into cheese.",
    "A story that teaches kids why it is important to tell the truth.",
    "A story about a girl who learns that being different is a strength.",
    "A very silly story about a talking sandwich who wants to go to school.",
    "A story about a king who hiccups every time he tries to give a royal speech.",
    "A story about two brothers who find a mysterious glowing box in their backyard.",
    "A story about a kid who discovers their shadow is doing things they did not do.",
    "A story about a curious girl who shrinks down to explore the inside of a flower.",
    "A story about a girl who invents a machine that translates animal sounds.",
    "A story about a robot and a puppy who become unlikely best friends.",
    "A story about a new kid at school who is too shy to talk to anyone.",
    "A story about a bear who keeps accidentally sitting on things and squishing them flat.",
    "A story about a girl who is scared of the dark but has to save her little brother.",
    "A story about a grandma who secretly knows magic.",
    "A story about a boy who learns to say sorry even when it is hard.",
    "A story about a dog who is convinced the vacuum cleaner is a monster.",
    "A story about a girl who wakes up and finds her toys have been rearranged overnight.",
    "A story about a little girl who misses her grandpa.",
    "A story about a child who is moving to a new town and does not want to leave their friends.",
    "Tell me a bedtime story.",
    "A story about twins who swap lives for a day and discover something surprising.",
    "A funny story for my 5 year old.",
    "A story about a boy who finds a map that leads to his backyard.",
    "A story about a fish who wants to climb a tree.",
    "A story about a kid who gets lost in a library and finds a door to another world.",
]


def main():
    cfg = StoryConfig()
    results = []

    for i, prompt in enumerate(PROMPTS, 1):
        print(f"[{i}/{len(PROMPTS)}] {prompt[:65]}", flush=True)
        try:
            state = run_pipeline(prompt, cfg)
            evaluation = state.get("evaluation", {})
            g = state.get("classification", {}).get("genre", "")
            sc = round(evaluation.get("overall", 0), 2)
            wc = len(state.get("story", "").split())
            fk = evaluation.get("reading_level_grade", 0)
            it = state.get("iteration_count", 0)
            results.append({
                "id": i,
                "request": prompt,
                "story": state.get("story", ""),
                "genre": g,
                "score": sc,
                "scores": evaluation.get("scores", {}),
                "iterations": it,
                "word_count": wc,
                "fk_grade": fk,
                "judge_feedback": evaluation.get("critique", ""),
            })
            print(f"  genre={g} score={sc} words={wc} fk={fk}", flush=True)
        except Exception as e:
            print(f"  ERROR: {e}", flush=True)
            results.append({"id": i, "request": prompt, "error": str(e)})
        time.sleep(1)

    with open("test_all.json", "w") as f:
        json.dump(results, f, indent=2)

    scores_list = [r["score"] for r in results if "score" in r and r["score"]]
    errors = [r for r in results if "error" in r]
    print(f"\nDone. {len(results)} stories, {len(errors)} errors.")
    if scores_list:
        print(f"Avg score: {sum(scores_list)/len(scores_list):.2f}")
        print(f"Min: {min(scores_list):.2f}  Max: {max(scores_list):.2f}")


if __name__ == "__main__":
    main()
