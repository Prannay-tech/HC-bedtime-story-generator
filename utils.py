import os
import json
import time
import logging
from dataclasses import dataclass, field
from typing import Any

import openai

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("story_pipeline")


@dataclass
class StoryConfig:
    model: str = "gpt-3.5-turbo"
    judge_threshold: float = 8.0
    max_iterations: int = 3
    storyteller_temperature: float = 0.85
    judge_temperature: float = 0.1
    planner_temperature: float = 0.3
    classifier_temperature: float = 0.1
    refiner_temperature: float = 0.7
    min_words: int = 300
    max_tokens_story: int = 1200
    max_tokens_plan: int = 600
    max_tokens_judge: int = 600
    max_tokens_classifier: int = 200
    retry_attempts: int = 3
    retry_base_delay: float = 1.5


@dataclass
class PipelineTrace:
    user_request: str = ""
    classification: dict = field(default_factory=dict)
    plan: dict = field(default_factory=dict)
    iterations: list = field(default_factory=list)
    final_story: str = ""
    total_calls: int = 0


def call_model(
    messages: list[dict],
    config: StoryConfig,
    temperature: float | None = None,
    max_tokens: int | None = None,
    json_mode: bool = False,
) -> str:
    openai.api_key = os.getenv("OPENAI_API_KEY")
    if not openai.api_key:
        raise EnvironmentError("OPENAI_API_KEY environment variable not set.")

    kwargs: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "temperature": temperature if temperature is not None else config.storyteller_temperature,
        "max_tokens": max_tokens if max_tokens is not None else config.max_tokens_story,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(1, config.retry_attempts + 1):
        try:
            resp = openai.ChatCompletion.create(**kwargs)
            return resp.choices[0].message["content"].strip()
        except openai.error.RateLimitError:
            if attempt == config.retry_attempts:
                raise
            delay = config.retry_base_delay ** attempt
            logger.warning("Rate limited. Retrying in %.1fs (attempt %d/%d).", delay, attempt, config.retry_attempts)
            time.sleep(delay)
        except openai.error.OpenAIError as e:
            logger.error("OpenAI API error: %s", e)
            raise


def parse_json(raw: str, context: str = "") -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Attempt to extract JSON block from markdown fences
        import re
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        logger.warning("Failed to parse JSON%s. Raw output:\n%s", f" ({context})" if context else "", raw)
        return {}
