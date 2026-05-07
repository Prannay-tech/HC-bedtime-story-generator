# System Block Diagram

Built with **LangGraph** — each box is a graph node, each arrow is an edge.
Conditional edges handle routing based on quality gate results.

```
                        ┌─────────────┐
                        │    START    │
                        └──────┬──────┘
                               │ user request
                               ▼
                    ┌──────────────────────┐
                    │   CLASSIFY NODE      │
                    │                      │
                    │  genre, tone,        │
                    │  themes, target age  │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    PLAN NODE         │
                    │                      │
                    │  title, characters,  │
                    │  5-beat structure    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    DRAFT NODE        │
                    │                      │
                    │  genre-tailored      │
                    │  system prompt +     │
                    │  self-check          │
                    └──────────┬───────────┘
                               │
                    [words < 300?]
                    ┌──────────┴───────────┐
                   YES                     NO
                    │                      │
                    ▼                      │
         ┌─────────────────┐              │
         │  EXPAND NODE    │              │
         │                 │              │
         │  add dialogue,  │              │
         │  description    │              │
         └────────┬────────┘              │
                  │                       │
                  └──────────┬────────────┘
                             │
                             ▼
                  ┌─────────────────────────────────────────┐
                  │              JUDGE NODE                  │
                  │                                         │
                  │  5 quality dimensions (each has         │
                  │  an independent minimum score gate):    │
                  │                                         │
                  │  • content_safety      (min 7.0) 25%   │
                  │  • vocabulary_access.  (min 7.0) 20%   │
                  │  • coherence           (min 7.0) 20%   │
                  │  • narrative_arc       (min 7.0) 20%   │
                  │  • engagement          (min 6.0) 15%   │
                  │                                         │
                  │  FK grade — informational only          │
                  └──────────────┬──────────────────────────┘
                                 │
                   [all gates pass OR max iterations?]
                   ┌─────────────┴──────────────┐
                  YES                           NO
                   │                            │
                   ▼                            ▼
        ┌──────────────────┐       ┌────────────────────────┐
        │  FINALIZE NODE   │       │     REFINE NODE        │
        │                  │       │                        │
        │  set final_story │       │  targeted fixes for    │
        └────────┬─────────┘       │  each failing gate     │
                 │                 └────────────┬───────────┘
                 ▼                              │
              ┌─────┐              [words < 300?]
              │ END │         ┌────────┴────────┐
              └─────┘        YES               NO
                              │                 │
                              ▼                 │
                   ┌─────────────────┐          │
                   │  EXPAND NODE    │          │
                   └────────┬────────┘          │
                            │                   │
                            └─────────┬─────────┘
                                      │
                                      └────────► JUDGE NODE (loop)
```

## Node Summary

| Node | Role | Agent Class | Temp |
|---|---|---|---|
| classify | Extract genre, tone, themes, target age | `ClassifierAgent` | 0.1 |
| plan | Build 5-beat narrative structure | `PlannerAgent` | 0.3 |
| draft | Write full story with self-check | `StorytellerAgent` | 0.85 |
| expand | Add content if story is too short | `ExpandPass` | 0.7 |
| judge | Score 5 quality dimensions | `JudgeAgent` | 0.1 |
| refine | Fix failing dimensions and critique | `NarrativeRefinePass` | 0.7 |
| finalize | Set final_story in state | — | — |

## Quality Gates

Every story must pass **all** of these before the graph reaches END:

| Gate | What it checks | Min score |
|---|---|---|
| `content_safety` | No scary/adult themes. Safe for ages 5-10. | 7.0 |
| `vocabulary_accessibility` | Words a 7-year-old actually knows (not syllable counting) | 7.0 |
| `coherence` | Story makes logical sense, no plot holes | 7.0 |
| `narrative_arc` | Hook + rising action + climax + resolution all present | 7.0 |
| `engagement` | A child would want to hear it again | 6.0 |
| `word_count` | At least 300 words | — |
| `overall` | Weighted average of all dimensions | 8.0 |

## Why LangGraph

The pipeline is a **stateful graph with cycles** — exactly what LangGraph is designed for:
- The judge→refine loop is a native cycle, not a hand-rolled `for` loop
- Conditional routing (`route_after_judge`, `route_after_draft`) is a first-class construct
- `StoryState` (TypedDict) is the single shared state — no custom `PipelineTrace` class needed
- The graph is inspectable, serializable, and easy to extend with new nodes
- LangSmith tracing can be added with one environment variable for full observability

## File Structure

```
├── main.py           # Entry point, display, user feedback loop
├── graph.py          # LangGraph graph: nodes, edges, routing, run_pipeline()
├── state.py          # StoryState TypedDict — shared state across all nodes
├── agents.py         # Agent classes: Classifier, Planner, Storyteller, Expand, Judge, Refine
├── prompts.py        # All system/user prompts, judge rubric, weights, min scores
├── utils.py          # call_model (with retry), parse_json, StoryConfig
├── test_pipeline.py  # 16-story batch test runner with per-story checkpointing
├── diagram.md        # This file
└── requirements.txt
```
