from __future__ import annotations

import asyncio
import random
import re
from dataclasses import dataclass
from typing import AsyncIterator

from loguru import logger
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.google.llm import GoogleLLMService
from pipecat.utils.errors import ErrorCategory


@dataclass(frozen=True)
class GeminiFailure:
    http_status: int | None
    provider_status: str | None
    metric: str | None
    limit: str | None
    model: str | None
    retry_delay_seconds: int | None
    kind: str
    retryable: bool

    @property
    def public_message(self) -> str:
        if self.kind == "daily_quota":
            return "Gemini's daily request quota is exhausted. The call remains connected, but replies need the provider quota reset or a project with available quota."
        if self.kind in {"billing", "project_quota"}:
            return "Gemini is unavailable for this API project because its quota or billing limit has been reached. The call remains connected."
        return "The AI response service is temporarily unavailable. The call remains connected; please try again shortly."

    @property
    def category(self) -> ErrorCategory:
        return ErrorCategory.RATE_LIMIT if self.retryable else ErrorCategory.QUOTA


def _first_match(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1) if match else None


def classify_gemini_failure(error: BaseException) -> GeminiFailure:
    """Classify Google errors without retaining or logging their raw payload."""

    raw = str(error)
    status_value = getattr(error, "code", None) or getattr(error, "status", None)
    http_status = status_value if isinstance(status_value, int) else None
    if http_status is None:
        matched_status = _first_match(r"\b(429|500|502|503|504)\b", raw)
        http_status = int(matched_status) if matched_status else None

    provider_status = _first_match(r'"status"\s*:\s*"([A-Z_]+)"', raw)
    metric = _first_match(r'"quotaMetric"\s*:\s*"([^"]+)"', raw)
    limit = _first_match(r'"quotaValue"\s*:\s*"?([^",}\s]+)', raw)
    model = _first_match(r'"model"\s*:\s*"([^"]+)"', raw)
    retry_delay = _first_match(r'"retryDelay"\s*:\s*"(\d+)s"', raw)
    retry_delay_seconds = int(retry_delay) if retry_delay else None
    normalized = raw.lower()

    if "per day" in normalized or "perday" in (metric or "").lower():
        kind = "daily_quota"
    elif any(term in normalized for term in ("billing", "spend cap", "payment", "credit limit")):
        kind = "billing"
    elif metric and "perproject" in metric.lower():
        kind = "project_quota"
    elif http_status in {429} and any(term in normalized for term in ("per minute", "rpm", "tpm", "rate limit")):
        kind = "temporary_rate_limit"
    elif http_status in {500, 502, 503, 504} or provider_status == "UNAVAILABLE":
        kind = "provider_overload"
    else:
        kind = "other"

    # Retry only short-lived throttling/overload responses. A supplied delay
    # longer than the bounded call retry window is respected by not retrying.
    retryable = kind in {"temporary_rate_limit", "provider_overload"} and (
        retry_delay_seconds is None or retry_delay_seconds <= 30
    )
    return GeminiFailure(
        http_status=http_status,
        provider_status=provider_status,
        metric=metric,
        limit=limit,
        model=model,
        retry_delay_seconds=retry_delay_seconds,
        kind=kind,
        retryable=retryable,
    )


class ResilientGoogleLLMService(GoogleLLMService):
    """Google service with bounded retries for temporary provider failures only."""

    _max_provider_retries = 2

    async def _stream_response(self, context: LLMContext) -> AsyncIterator:
        attempts = 0
        while True:
            yielded_output = False
            try:
                async for chunk in super()._stream_response(context):
                    yielded_output = True
                    yield chunk
                return
            except Exception as error:
                failure = classify_gemini_failure(error)
                self._log_failure(failure)
                if yielded_output or not failure.retryable or attempts >= self._max_provider_retries:
                    raise
                exponential_delay = min(8.0, float(2**attempts))
                delay = failure.retry_delay_seconds if failure.retry_delay_seconds is not None else exponential_delay + random.uniform(0, 0.25)
                logger.info("Gemini temporary failure retry: attempt={}, delay_seconds={}", attempts + 1, delay)
                await asyncio.sleep(delay)
                attempts += 1

    async def push_error(self, error_msg: str, exception: Exception | None = None, **kwargs) -> None:
        if exception is not None:
            failure = classify_gemini_failure(exception)
            if failure.http_status is not None or failure.provider_status is not None:
                self._log_failure(failure)
                await super().push_error(
                    error_msg=failure.public_message,
                    exception=None,
                    category=failure.category,
                )
                return
        await super().push_error(error_msg=error_msg, exception=exception, **kwargs)

    @staticmethod
    def _log_failure(failure: GeminiFailure) -> None:
        logger.warning(
            "Gemini request failed: http_status={}, provider_status={}, kind={}, retryable={}, quota_metric={}, quota_limit={}, model={}, retry_delay_seconds={}",
            failure.http_status,
            failure.provider_status,
            failure.kind,
            failure.retryable,
            failure.metric,
            failure.limit,
            failure.model,
            failure.retry_delay_seconds,
        )
