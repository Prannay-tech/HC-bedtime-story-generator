# Hippocratic AI — Bedtime Story Generator

A multi-agent AI pipeline that takes any story request and produces a high-quality, age-appropriate bedtime story for children aged 5–10. The system uses a judge agent to iteratively improve each story, an objective readability check, and a user feedback loop for personalized changes.

---

## System Architecture

See [`diagram.md`](./diagram.md) for the full block diagram.

**Pipeline stages:**
```
User Request
    → Classifier   (genre, tone, themes, target age)
    → Planner      (5-beat narrative structure)
    → Storyteller  (full draft, genre-tailored prompt)
    → Judge        (weighted rubric + Flesch-Kincaid check)
    → Refiner      (targeted rewrite, up to 3 iterations)
    → Final Story + Scorecard
    → User Feedback Loop (optional targeted changes)
```

---

## Local Setup

### Prerequisites
- Python 3.10+
- An OpenAI API key

### Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd hippocratic-story-generator

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your OpenAI API key
export OPENAI_API_KEY=your-key-here
# On Windows: set OPENAI_API_KEY=your-key-here
```

### Run

```bash
python main.py
```

You'll be prompted to enter a story request. Example:

```
What kind of story do you want to hear?
> A story about a girl named Alice and her best friend Bob, who happens to be a cat.
```

The pipeline will run, print the story, display a scorecard, then ask if you'd like any changes.

---

## Project Structure

```
├── main.py           # Entry point, display, user feedback loop
├── agents.py         # All agents: Classifier, Planner, Storyteller, Judge, Refiner, Pipeline
├── prompts.py        # All system and user prompts, organized by agent and genre
├── utils.py          # call_model wrapper with retry logic, JSON parsing, config, trace
├── diagram.md        # Block diagram of the full system
├── requirements.txt
└── README.md
```

---

## Design Highlights

- **Structured planning before writing** — The Planner produces a JSON story plan (hook, beats, climax, resolution, moral) that the Storyteller follows precisely, preventing wandering narratives.
- **Weighted LLM judge** — Scores 5 dimensions (age-appropriateness 25%, narrative arc 25%, engagement 20%, character depth 15%, moral clarity 15%) and triggers targeted refinement if the overall score is below 8.0.
- **Objective readability validation** — Uses the Flesch-Kincaid formula (`textstat`) to flag stories above a 5th-grade reading level, independent of the LLM judge.
- **Genre-tailored prompts** — Each genre (adventure, animals, fantasy, friendship, mystery, humor, science) gets a specialized style note in the storyteller system prompt.
- **Targeted refinement** — The Refiner receives the specific critique and fix list rather than starting from scratch, reducing cost and improving precision.
- **User feedback loop** — After the story is delivered, natural language changes ("make it funnier", "add a dragon") are routed directly to the Refiner.

---

## Configuration

All pipeline parameters are in `utils.py` under `StoryConfig`:

| Parameter | Default | Description |
|---|---|---|
| `judge_threshold` | 8.0 | Minimum score to stop refining |
| `max_iterations` | 3 | Maximum judge–refine cycles |
| `storyteller_temperature` | 0.85 | Controls creativity of drafts |
| `judge_temperature` | 0.1 | Keeps scoring deterministic |
| `max_tokens_story` | 1200 | Token budget per story draft |

---

## Example Output

```
════════════════════════════════════════════════════════════════════════
             ✦  Bedtime Story Generator  ✦
         Powered by a multi-agent AI pipeline
════════════════════════════════════════════════════════════════════════

What kind of story do you want to hear?
> A story about a girl named Alice and her cat Bob

Generating your story — this may take a moment...

────────────────────────────────────────────────────────────────────────

  The Curious Case of Captain Bob

Alice loved many things: pancakes, puddles, and her cat Bob...

────────────────────────────────────────────────────────────────────────

  Pipeline summary
────────────────────────────────────────────────────────────────────────
  Iterations run     : 2
  Total API calls    : 6
  Final overall score: 8.45 / 10
  Reading level      : Grade 3.8 (target ≤ 5)

  Age appropriateness: ████████░░ 8.5
  Narrative arc      : █████████░ 9.0
  Engagement         : ████████░░ 8.0
  Character depth    : ████████░░ 8.0
  Moral clarity      : ████████░░ 8.5

  Strongest element  : vivid hook and strong emotional resolution
────────────────────────────────────────────────────────────────────────
```
