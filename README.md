# Hippocratic AI — Bedtime Story Generator

A multi-agent LangGraph pipeline that takes any story request and produces a high-quality,
age-appropriate bedtime story for children aged 5–10. The system uses a structured planning
stage, a calibrated LLM judge, iterative refinement, and an objective readability check.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your API key
export OPENAI_API_KEY=your-key-here

# 3. Run
python main.py
```

You will be prompted for a story request:

```
What kind of story do you want to hear?
> A story about a girl who is scared of the dark but has to save her little brother.
```

The pipeline runs, prints the story, shows a scorecard, then asks if you want any changes.

---

## Pipeline Architecture

```
User Request
    ↓
Classifier    →  genre, tone, themes, target age (5–7 or 7–10)
    ↓
Planner       →  title, characters, 5-beat structure, moral, tone notes
    ↓
Storyteller   →  full draft with genre-tailored prompt + 5 few-shot examples
    ↓
[word count < min?]  →  Expander  →  back to Judge
    ↓
Judge         →  5-dimension weighted score + Flesch-Kincaid reading level
    ↓
[score ≥ 8.0 and all gates pass?]  →  Finalize  →  Output
    ↓  [else, up to 3 iterations]
Refiner       →  targeted rewrite based on specific critique
    ↓  back to Judge
```

Implemented as a **LangGraph `StateGraph`** with conditional routing. Each node is a pure
function that reads from `StoryState` and returns only the keys it updates. Config is
passed via closures, not stored in state — this avoids LangGraph's restriction that state
keys must be declared in the `TypedDict`.

---

## Design Decisions and Reasoning

### 1. Why a Classifier first?

A story prompt like "A funny story for my 5 year old" contains no explicit genre. Without
classification, the storyteller would guess — and usually guess wrong (defaulting to fantasy
when humor is clearly intended). The classifier extracts genre, tone, and estimated target age
(5–7 vs 7–10), which drives both the storyteller's style note and the judge's age calibration.

### 2. Why a separate Planner?

Writing a full story directly from a one-line prompt produces wandering narratives with weak
structure — the model fills space rather than building toward a resolution. The Planner forces
commitment to a 5-beat structure (hook, rising action ×2, climax, resolution) and a named
moral before any prose is written. The Storyteller then executes a plan rather than improvising
one — this is the single biggest quality improvement in the pipeline.

### 3. Why few-shot examples in the Storyteller?

GPT-3.5-turbo's default children's story style is generic: long sentences, abstract vocabulary,
explicit moral declarations. Five annotated examples teach the model the specific register we
want — short sentences, character-specific dialogue, morals shown through action. The examples
were chosen to cover fundamentally different story types (friction-adventure, mood/no-conflict,
deadpan humor, action-moral, animal-belonging) so the model learns principles rather than
copying a single template. Too many examples risk homogenization; five is the identified sweet
spot for this task.

### 4. Why a weighted LLM judge instead of just Flesch-Kincaid?

Flesch-Kincaid measures sentence length and syllable count — it catches vocabulary problems
but cannot evaluate whether a story has a satisfying arc, age-appropriate emotional stakes,
or engaging characters. The judge scores five dimensions independently:

| Dimension | Weight | What it catches |
|---|---|---|
| content_safety | 25% | Scary, violent, or adult-inappropriate content |
| vocabulary_accessibility | 20% | Complex words, adult phrasings, long sentences |
| coherence | 20% | Premise abandoned mid-story, plot holes |
| narrative_arc | 20% | No change from start to end, effortless climax |
| engagement | 15% | Generic emotional filler, no memorable moments |

The overall score is **recalculated server-side** from dimension scores — the model's
self-reported overall is ignored. This prevents a common failure mode where the judge scores
7, 8, 8, 9, 9 on dimensions but reports "overall: 9.5."

Flesch-Kincaid is used as a **secondary signal**: if FK > 8.0, the judge prompt is nudged
to scrutinize vocabulary more carefully. FK alone does not gate the story.

### 5. Why per-dimension minimum gates?

An overall score of 8.2 can hide a content_safety score of 6.0. Each dimension has an
independent minimum (content_safety: 8.0, all others: 7.0). A story that passes overall
but fails any single dimension still goes to refinement. This prevents safe-looking aggregate
scores from masking serious failures.

### 6. Why a targeted Refiner rather than a full rewrite?

Re-generating from scratch on a low score throws away what worked. The Refiner receives the
specific critique and a prioritized fix list — failing dimensions first, then word count if
needed, then general feedback. It rewrites to fix those specific issues while preserving the
structure and characters. This reduces token cost and produces more consistent improvements
than a blank-slate regeneration.

### 7. Why a separate Expand pass?

If a draft comes in under the minimum word count, expanding it inside the Storyteller prompt
creates a conflict: the model tries to write a good story AND hit a word count at the same
time, often padding badly. The Expander is a dedicated editor pass with a single job — add
dialogue, descriptions, and scene texture without changing the plot. Separation of concerns
produces cleaner results.

---

## Judge Calibration

The judge was calibrated to avoid two common failure modes:

**Inflation** — LLMs are trained to be helpful and tend to score their own output highly.
Without explicit calibration, the judge scores 9.2–9.6 on every story regardless of quality.
The system prompt includes: "If every dimension scores 8+, you are almost certainly being
too lenient. A passing story earns 7–8. Reserve 9+ for something genuinely memorable."

**Content safety inflation** — A simply safe story is not a 10/10 on safety. The judge is
told: "A story with no safety concerns earns 7–8. A 10 means exceptional care with a
difficult theme like illness, death, or fear."

After calibration across 30 test stories, the judge average is 8.90 with a range of 8.0–9.45,
which reflects realistic quality variation rather than uniform inflation.

---

## Project Structure

```
├── main.py           — Entry point, display, user feedback loop
├── graph.py          — LangGraph StateGraph, routing logic, run_pipeline()
├── agents.py         — All agent classes: Classifier, Planner, Storyteller, Judge, Refiner
├── prompts.py        — All prompts organized by agent, genre style notes, few-shot examples
├── state.py          — StoryState TypedDict definition
├── utils.py          — call_model() with retry, StoryConfig, JSON parsing
├── observability.py  — LangSmith tracing helpers (optional)
├── run_test_all.py   — Batch test runner (30 prompts)
├── test_all.json     — Latest batch test results
└── requirements.txt
```

---

## Configuration

All parameters live in `StoryConfig` in `utils.py`:

| Parameter | Default | Description |
|---|---|---|
| `judge_threshold` | 8.0 | Minimum overall score to accept story |
| `max_iterations` | 3 | Maximum judge–refine cycles |
| `min_words` | 300 | Minimum story length |
| `storyteller_temperature` | 0.85 | Draft creativity |
| `judge_temperature` | 0.1 | Scoring determinism |
| `refiner_temperature` | 0.7 | Refinement creativity |

---

## Test Results

Batch of 30 diverse prompts covering 7 genres (adventure, fantasy, friendship, humor, moral,
mystery, science). All prompts completed with 0 errors.

| Metric | Value |
|---|---|
| Prompts tested | 30 |
| Pass rate (score ≥ 8.0) | 100% |
| Average judge score | 8.90 / 10 |
| Average word count | 383 |
| Average FK grade | 5.7 |
| Stories requiring 0 refinements | 23 / 30 |
| Stories requiring 1 refinement | 5 / 30 |
| Stories requiring 2 refinements | 2 / 30 |

---

## Optional: LangSmith Observability

Set these environment variables to enable full trace logging in LangSmith:

```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=your-langsmith-key
export LANGCHAIN_PROJECT=hippocratic-story-generator
```

Each run logs genre, score, word count, FK grade, iteration count, and dimension scores
to the LangSmith project for analysis across runs.
