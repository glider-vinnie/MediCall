from app.voice.gemini import classify_gemini_failure


def test_daily_free_tier_quota_is_not_retryable() -> None:
    error = RuntimeError(
        '429 Too Many Requests {"error":{"status":"RESOURCE_EXHAUSTED",'
        '"message":"Generate content requests per day limit exceeded on Free Tier",'
        '"details":[{"@type":"type.googleapis.com/google.rpc.QuotaFailure",'
        '"violations":[{"quotaMetric":"generativelanguage.googleapis.com/generate_content_free_tier_requests",'
        '"quotaValue":"20","quotaDimensions":{"model":"gemini-3.6-flash"}}]},'
        '{"@type":"type.googleapis.com/google.rpc.RetryInfo","retryDelay":"54247s"}]}}'
    )

    failure = classify_gemini_failure(error)

    assert failure.http_status == 429
    assert failure.provider_status == "RESOURCE_EXHAUSTED"
    assert failure.metric == "generativelanguage.googleapis.com/generate_content_free_tier_requests"
    assert failure.limit == "20"
    assert failure.model == "gemini-3.6-flash"
    assert failure.retry_delay_seconds == 54247
    assert failure.kind == "daily_quota"
    assert failure.retryable is False


def test_temporary_rate_limit_is_retryable_when_its_delay_is_bounded() -> None:
    failure = classify_gemini_failure(
        RuntimeError('429 {"status":"RESOURCE_EXHAUSTED","message":"requests per minute rate limit","retryDelay":"2s"}')
    )

    assert failure.kind == "temporary_rate_limit"
    assert failure.retryable is True
    assert failure.retry_delay_seconds == 2
