"""Asks Claude (with live web search) for an ARV estimate and returns it validated.

Claude answers by calling the `submit_arv_estimate` tool whose input schema is
`ArvEstimateRes`, rather than through JSON output mode: web search answers carry
citations, which JSON output mode rejects, while a tool call's input is plain
JSON. The input is then validated with Pydantic, so nothing reaches the UI that
does not match the template.

The API key is read from `ANTHROPIC_API_KEY` on the backend only and held in a
`Secret`; it is never sent to the browser.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any
from urllib.parse import urlparse

import anthropic
from pydantic import ValidationError

from BL.arvEstimate.common.arv_estimate_prompts import (
    SUBMIT_ARV_ESTIMATE_TOOL_NAME,
    build_arv_estimate_system_prompt,
    build_arv_estimate_user_message,
)
from BL.common.secret import Secret
from ReqRes.common.arv_estimate_schemas import ArvEstimateReq, ArvEstimateRes

logger = logging.getLogger(__name__)

DEFAULT_ARV_ESTIMATE_MODEL = "claude-opus-5-5"
ARV_ESTIMATE_MAX_OUTPUT_TOKENS = 16000
ARV_ESTIMATE_MAX_WEB_SEARCHES = 15
# Each Claude request may pause (server-side search loop limit) or end without
# the tool call; this caps how many follow-up requests one estimate may cost.
ARV_ESTIMATE_MAX_CLAUDE_REQUESTS = 6
ARV_ESTIMATE_SECONDS_PER_CLAUDE_REQUEST = 300
# If Claude's safety classifiers decline, the API re-runs the request on the
# recommended fallback model instead of returning a refusal.
SERVER_SIDE_FALLBACK_BETA = "server-side-fallback-2026-07-01"

NUDGE_TO_SUBMIT_ARV_ESTIMATE = (
    f"Please call the {SUBMIT_ARV_ESTIMATE_TOOL_NAME} tool now with your final answer, "
    "using the comparables you have already found."
)


class ArvEstimateNotConfiguredError(RuntimeError):
    """`ANTHROPIC_API_KEY` is not set on the server."""


class ArvEstimateFailedError(RuntimeError):
    """The estimate could not be produced. The message is safe to show the user."""


def anthropic_api_key() -> Secret:
    return Secret((os.getenv("ANTHROPIC_API_KEY") or "").strip())


def arv_estimate_model() -> str:
    return (os.getenv("ARV_ESTIMATE_MODEL") or "").strip() or DEFAULT_ARV_ESTIMATE_MODEL


def build_submit_arv_estimate_tool() -> dict[str, Any]:
    return {
        "name": SUBMIT_ARV_ESTIMATE_TOOL_NAME,
        "description": (
            "Submit the finished ARV estimate. Call exactly once, after researching the comparables, "
            "with every field of the template filled (null where a fact could not be found)."
        ),
        "input_schema": ArvEstimateRes.model_json_schema(),
    }


def build_web_search_tool() -> dict[str, Any]:
    return {"type": "web_search_20260209", "name": "web_search", "max_uses": ARV_ESTIMATE_MAX_WEB_SEARCHES}


def _submitted_arv_estimate_input(response_content: list[Any]) -> dict[str, Any] | None:
    for block in response_content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == SUBMIT_ARV_ESTIMATE_TOOL_NAME:
            submitted_input = getattr(block, "input", None)
            return submitted_input if isinstance(submitted_input, dict) else None
    return None


def _is_web_url(candidate_url: str | None) -> bool:
    if not candidate_url:
        return False
    parsed_url = urlparse(candidate_url.strip())
    return parsed_url.scheme in {"http", "https"} and bool(parsed_url.netloc)


def sanitize_arv_estimate(arv_estimate: ArvEstimateRes) -> ArvEstimateRes:
    """Keep only http(s) links (they are rendered as anchors) and make the numbers consistent."""
    for comparable in arv_estimate.sold_comparables + arv_estimate.active_or_pending_comparables:
        if not _is_web_url(comparable.source_url):
            comparable.source_url = None
    arv_estimate.source_urls = [url.strip() for url in arv_estimate.source_urls if _is_web_url(url)]
    arv_estimate.estimated_arv_range_low = min(arv_estimate.estimated_arv_range_low, arv_estimate.target_arv)
    arv_estimate.estimated_arv_range_high = max(arv_estimate.estimated_arv_range_high, arv_estimate.target_arv)
    arv_estimate.conservative_lowest_arv = min(arv_estimate.conservative_lowest_arv, arv_estimate.target_arv)
    return arv_estimate


def _create_claude_message(anthropic_client: Any, system_prompt: str, messages: list[dict[str, Any]]) -> Any:
    return anthropic_client.beta.messages.create(
        model=arv_estimate_model(),
        max_tokens=ARV_ESTIMATE_MAX_OUTPUT_TOKENS,
        # The system prompt is the same for every estimate of a deal type, so it is cached.
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=messages,
        tools=[build_web_search_tool(), build_submit_arv_estimate_tool()],
        output_config={"effort": "high"},
        betas=[SERVER_SIDE_FALLBACK_BETA],
        fallbacks="default",
    )


def request_arv_estimate_from_claude(
    arv_estimate_request: ArvEstimateReq,
    *,
    anthropic_client: Any = None,
    today: date | None = None,
) -> ArvEstimateRes:
    api_key = anthropic_api_key()
    if anthropic_client is None:
        if not api_key:
            raise ArvEstimateNotConfiguredError("ARV estimate is not configured (ANTHROPIC_API_KEY is not set).")
        anthropic_client = anthropic.Anthropic(
            api_key=api_key.reveal(),
            timeout=ARV_ESTIMATE_SECONDS_PER_CLAUDE_REQUEST,
            max_retries=2,
        )

    system_prompt = build_arv_estimate_system_prompt(arv_estimate_request.deal_type)
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": build_arv_estimate_user_message(arv_estimate_request, today=today)}
    ]
    already_nudged_to_submit = False

    for _ in range(ARV_ESTIMATE_MAX_CLAUDE_REQUESTS):
        try:
            response = _create_claude_message(anthropic_client, system_prompt, messages)
        except anthropic.AuthenticationError as error:
            logger.error("ARV estimate: Anthropic rejected the API key (status %s)", error.status_code)
            raise ArvEstimateFailedError("The server's Anthropic API key was rejected.") from error
        except anthropic.RateLimitError as error:
            raise ArvEstimateFailedError("Claude is busy right now; try again in a minute.") from error
        except anthropic.APIStatusError as error:
            logger.error("ARV estimate: Anthropic API error status=%s", error.status_code)
            raise ArvEstimateFailedError("Claude could not be reached; try again later.") from error
        except anthropic.APIConnectionError as error:
            raise ArvEstimateFailedError("Claude could not be reached; try again later.") from error

        if response.stop_reason == "refusal":
            raise ArvEstimateFailedError("Claude declined to estimate this property.")

        submitted_input = _submitted_arv_estimate_input(response.content)
        if submitted_input is not None:
            try:
                return sanitize_arv_estimate(ArvEstimateRes.model_validate(submitted_input))
            except ValidationError as error:
                logger.warning("ARV estimate: Claude's answer did not match the template: %s", error.error_count())
                raise ArvEstimateFailedError("Claude's answer did not match the expected template; try again.") from error

        if response.stop_reason == "max_tokens":
            raise ArvEstimateFailedError("Claude's answer was cut off before it finished; try again.")

        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "pause_turn":
            # The server-side search loop paused; resending the turn resumes it.
            continue
        if already_nudged_to_submit:
            break
        messages.append({"role": "user", "content": NUDGE_TO_SUBMIT_ARV_ESTIMATE})
        already_nudged_to_submit = True

    raise ArvEstimateFailedError("Claude did not return an ARV estimate; try again.")
