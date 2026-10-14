import os
import re
import json
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from app.core.config import settings

logger = logging.getLogger(__name__)

class GeminiQuotaExceededError(RuntimeError):
    """
    Raised when Gemini API encounters HTTP 429 or RESOURCE_EXHAUSTED.
    Carries structured, sanitized application error metadata without provider internals.
    """
    def __init__(
        self,
        message: Optional[str] = None,
        retry_delay_seconds: Optional[float] = None,
        retry_after_human: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        base_msg = "Live AI generation is temporarily unavailable because the AI service has reached its current usage limit. Please try again later."
        if message and "temporarily unavailable" in message.lower():
            self.message = message
        elif retry_after_human:
            self.message = f"{base_msg} (estimated retry {retry_after_human})."
        else:
            self.message = base_msg

        super().__init__(self.message)
        self.retry_delay_seconds = retry_delay_seconds
        self.retry_after_human = retry_after_human
        self.original_error = original_error

def is_gemini_quota_error(err: Exception) -> bool:
    """
    Detect Gemini quota / rate-limit errors, including HTTP 429 and RESOURCE_EXHAUSTED.
    """
    if isinstance(err, GeminiQuotaExceededError):
        return True

    status_code = (
        getattr(err, "code", None)
        or getattr(err, "status_code", None)
        or getattr(getattr(err, "response", None), "status_code", None)
    )
    if status_code == 429:
        return True

    err_str = str(err).lower()
    quota_signatures = [
        "resource_exhausted",
        "resource has been exhausted",
        "check quota",
        "429",
        "quota exceeded",
        "quota limit",
        "rate limit",
        "rate_limit",
        "generativelanguage.googleapis.com/generate_content_free_tier_requests",
        "generaterequestsperdayperprojectpermodel-freetier",
        "too many requests",
        "exceeded your current quota",
        "quota_exceeded",
        "temporarily unavailable because the ai service has reached its current usage limit"
    ]
    return any(sig in err_str for sig in quota_signatures)

class GeminiServiceUnavailableError(RuntimeError):
    """
    Raised when Gemini API encounters HTTP 503 or SERVICE_UNAVAILABLE (high demand / overloaded)
    after exhausting retries.
    """
    def __init__(
        self,
        message: Optional[str] = None,
        retry_delay_seconds: Optional[float] = None,
        retry_after_human: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        base_msg = "Live AI generation is temporarily unavailable due to high model demand. Please try again in a few moments."
        if message and "temporarily unavailable" in message.lower():
            self.message = message
        elif retry_after_human:
            self.message = f"{base_msg} (estimated retry {retry_after_human})."
        else:
            self.message = base_msg

        super().__init__(self.message)
        self.retry_delay_seconds = retry_delay_seconds
        self.retry_after_human = retry_after_human
        self.original_error = original_error

def is_gemini_transient_error(err: Exception) -> bool:
    """
    Detect transient Gemini errors eligible for bounded retry, including HTTP 503 and SERVICE_UNAVAILABLE.
    CRITICAL: 429 quota errors are NOT transient 503 errors and must NOT enter the 503 retry loop.
    """
    if not err:
        return False

    if isinstance(err, GeminiServiceUnavailableError):
        return True

    # Quota errors must never be treated as transient 503 overload errors
    if is_gemini_quota_error(err):
        return False

    status_code = (
        getattr(err, "code", None)
        or getattr(err, "status_code", None)
        or getattr(getattr(err, "response", None), "status_code", None)
    )
    if status_code in (503, 502, 504):
        return True

    err_str = str(err).lower()
    transient_signatures = [
        "503",
        "service_unavailable",
        "service unavailable",
        "high demand",
        "spikes in demand are usually temporary",
        "model is overloaded",
        "model is currently experiencing high demand",
        "currently experiencing high demand",
        "the model is overloaded",
        "unavailable",
        "bad gateway",
        "gateway timeout",
        "connection reset",
        "temporarily overloaded"
    ]
    return any(sig in err_str for sig in transient_signatures)

def format_human_retry_delay(seconds: float) -> str:
    """
    Formats retry seconds into a friendly, non-promising estimate.
    """
    if seconds <= 0:
        return "in a few moments"
    elif seconds < 60:
        return "in about a minute"
    elif seconds < 3600:
        minutes = max(1, round(seconds / 60))
        return f"in about {minutes} minute{'s' if minutes != 1 else ''}"
    else:
        hours = round(seconds / 3600, 1)
        if hours.is_integer():
            hours = int(hours)
        return f"in approximately {hours} hour{'s' if hours != 1 else ''}"

def extract_gemini_retry_delay(err: Optional[Exception]) -> Tuple[Optional[float], Optional[str]]:
    """
    Extracts optional retry delay from Gemini provider error if supplied.
    Returns (seconds, human_estimate) or (None, None).
    Never exposes raw secrets or provider internals.
    """
    if not err:
        return None, None

    if isinstance(err, GeminiQuotaExceededError):
        if err.retry_delay_seconds is not None:
            return err.retry_delay_seconds, err.retry_after_human or format_human_retry_delay(err.retry_delay_seconds)
        if err.retry_after_human is not None:
            return None, err.retry_after_human

    # Check response headers if present
    resp = getattr(err, "response", None)
    if resp is not None:
        headers = getattr(resp, "headers", {})
        if headers:
            retry_header = headers.get("retry-after") or headers.get("Retry-After")
            if retry_header:
                try:
                    sec = float(retry_header)
                    return sec, format_human_retry_delay(sec)
                except (ValueError, TypeError):
                    pass

    err_str = str(err)

    # 1. Look for retryDelay in JSON/dict: 'retryDelay': '35088s' or 'retryDelay': 60
    delay_match = re.search(r"['\"]retryDelay['\"]\s*:\s*['\"]?(\d+(?:\.\d+)?)\s*s?['\"]?", err_str, re.IGNORECASE)
    if delay_match:
        try:
            seconds = float(delay_match.group(1))
            return seconds, format_human_retry_delay(seconds)
        except (ValueError, TypeError):
            pass

    # 2. Look for 'retry in Xh Ym Zs'
    retry_in_match = re.search(r"retry in\s+([0-9hms\.]+)", err_str, re.IGNORECASE)
    if retry_in_match:
        raw_dur = retry_in_match.group(1)
        total_sec = 0.0
        h_match = re.search(r"(\d+)h", raw_dur)
        m_match = re.search(r"(\d+)m", raw_dur)
        s_match = re.search(r"(\d+(?:\.\d+)?)s", raw_dur)
        if h_match:
            total_sec += int(h_match.group(1)) * 3600
        if m_match:
            total_sec += int(m_match.group(1)) * 60
        if s_match:
            total_sec += float(s_match.group(1))
        if total_sec > 0:
            return total_sec, format_human_retry_delay(total_sec)

    # 3. Look for 'retry after X seconds'
    after_match = re.search(r"retry\s+after\s+(\d+(?:\.\d+)?)\s*(?:seconds|s)?", err_str, re.IGNORECASE)
    if after_match:
        try:
            seconds = float(after_match.group(1))
            return seconds, format_human_retry_delay(seconds)
        except (ValueError, TypeError):
            pass

    return None, None

def get_friendly_quota_message(err: Optional[Exception] = None, retry_after_human: Optional[str] = None) -> str:
    """
    Build user-facing friendly message adhering to Requirement 3:
    'Live AI generation is temporarily unavailable because the AI service has reached its current usage limit. Please try again later.'
    With optional human-readable retry estimate.
    """
    base_msg = "Live AI generation is temporarily unavailable because the AI service has reached its current usage limit. Please try again later."
    human_delay = retry_after_human
    if not human_delay and err:
        _, human_delay = extract_gemini_retry_delay(err)
    if human_delay:
        return f"{base_msg} (estimated retry {human_delay})."
    return base_msg

def get_friendly_service_unavailable_message(err: Optional[Exception] = None, retry_after_human: Optional[str] = None) -> str:
    """
    Build user-facing friendly message for transient service unavailability:
    'Live AI generation is temporarily unavailable due to high model demand. Please try again in a few moments.'
    With optional human-readable retry estimate.
    """
    base_msg = "Live AI generation is temporarily unavailable due to high model demand. Please try again in a few moments."
    human_delay = retry_after_human
    if not human_delay and err:
        _, human_delay = extract_gemini_retry_delay(err)
    if human_delay:
        return f"{base_msg} (estimated retry {human_delay})."
    return base_msg

def sanitize_error(err: Exception) -> str:
    """
    Sanitize error message to prevent exposure of API keys, authorization headers,
    raw provider exception objects, or full internal stack traces.
    """
    if is_gemini_quota_error(err):
        return get_friendly_quota_message(err)

    if is_gemini_transient_error(err):
        return get_friendly_service_unavailable_message(err)

    msg = str(err)
    for key_attr in ["GEMINI_API_KEY", "GROQ_API_KEY", "NVIDIA_API_KEY"]:
        val = getattr(settings, key_attr, None)
        if isinstance(val, str) and val:
            msg = msg.replace(val, "[REDACTED_API_KEY]")
        env_val = os.environ.get(key_attr)
        if isinstance(env_val, str) and env_val:
            msg = msg.replace(env_val, "[REDACTED_API_KEY]")
    msg = re.sub(r'AIza[0-9A-Za-z-_]{35}', '[REDACTED_API_KEY]', msg)
    msg = re.sub(r'gsk_[A-Za-z0-9_-]{20,}', '[REDACTED_API_KEY]', msg)
    msg = re.sub(r'nvapi-[A-Za-z0-9_-]{20,}', '[REDACTED_API_KEY]', msg)
    msg = re.sub(r'key=[A-Za-z0-9_\-]+', 'key=[REDACTED]', msg)
    msg = re.sub(r'Bearer\s+[A-Za-z0-9_\-]+', 'Bearer [REDACTED]', msg)

    # Scrub raw provider JSON/dict payloads to avoid leaking internals
    if "{'error':" in msg or '{"error":' in msg:
        inner_match = re.search(r"['\"]message['\"]\s*:\s*['\"]([^'\"]+)['\"]", msg)
        if inner_match:
            clean_inner = inner_match.group(1).split("\n")[0].strip()
            if any(k in clean_inner.lower() for k in ["quota", "resource_exhausted", "rate limit", "429"]):
                return get_friendly_quota_message(err)
            if any(k in clean_inner.lower() for k in ["503", "unavailable", "high demand", "overloaded"]):
                return get_friendly_service_unavailable_message(err)
            return f"Gemini API error: {clean_inner}"
        return "Gemini API error: The upstream service returned an unhandled error."

    # Scrub internal URLs and GCP paths
    msg = re.sub(r'https?://generativelanguage\.googleapis\.com[^\s\'"]*', '[API_ENDPOINT]', msg)
    msg = re.sub(r'projects/[0-9]+/locations/[^/\s\'"]+/models/[^/\s\'"]+', '[MODEL_PATH]', msg)

    return msg

class GeminiService:
    """
    Multimodal Gemini service wrapper supporting:
    - Official google-genai SDK integration
    - Text reasoning & tutoring with structured JSON / Pydantic validation
    - Multimodal diagram/figure description
    - Video transcript understanding
    - Semantic vector embeddings (768 dimensions)
    - Deterministic fallback ONLY for explicit offline mode (when key is absent)
    - Strict error propagation when live mode is enabled (no silent fallback)
    - Safe rate-limit cooldown and quota error sanitization
    """
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
        self.model_name = settings.GEMINI_MODEL
        self.multimodal_model_name = settings.GEMINI_MULTIMODAL_MODEL
        self.embedding_model_name = settings.GEMINI_EMBEDDING_MODEL
        self.embedding_dimension = getattr(settings, "EMBEDDING_DIMENSION", 768)
        self._client = None
        self._verified_live: Optional[bool] = None
        self._quota_cooldown_until: Optional[float] = None
        self._last_quota_error: Optional[GeminiQuotaExceededError] = None
        self._init_client()

    def _init_client(self):
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not configured. Running in explicit offline simulation mode.")
            self._client = None
            return

        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
            logger.info("Initialized Google GenAI Client with official SDK.")
        except Exception as e:
            sanitized = sanitize_error(e)
            logger.error(f"Failed to initialize google.genai Client: {sanitized}")
            self._client = None

    def is_configured(self) -> bool:
        """
        Returns True if the active AI provider is configured.
        If AI_PROVIDER is set to groq or nvidia, delegates to that provider.
        If settings is mocked or AI_PROVIDER is gemini, checks the Gemini client.
        """
        raw_p = getattr(settings, "AI_PROVIDER", "gemini")
        if isinstance(raw_p, str) and raw_p.strip().lower() not in ("gemini", "google", "google-genai"):
            try:
                from app.core.ai_provider import get_ai_provider
                return get_ai_provider().is_configured()
            except Exception:
                pass
        return self.is_gemini_configured()

    def is_gemini_configured(self) -> bool:
        return self._client is not None and bool(self.api_key)

    def is_quota_exhausted(self) -> bool:
        """Returns True if the active service is currently within a quota exhaustion cooldown window."""
        raw_p = getattr(settings, "AI_PROVIDER", "gemini")
        if isinstance(raw_p, str) and raw_p.strip().lower() not in ("gemini", "google", "google-genai"):
            try:
                from app.core.ai_provider import get_ai_provider
                p = get_ai_provider()
                if hasattr(p, "is_quota_exhausted"):
                    return p.is_quota_exhausted()
            except Exception:
                pass
        return self._quota_cooldown_until is not None and time.time() < self._quota_cooldown_until

    def get_remaining_cooldown_seconds(self) -> float:
        if not self.is_quota_exhausted():
            return 0.0
        return max(0.0, (self._quota_cooldown_until or 0.0) - time.time())

    def reset_quota_cooldown(self):
        """Manually resets the quota cooldown (useful for testing or after key rotation)."""
        self._quota_cooldown_until = None
        self._last_quota_error = None

    def _check_quota_cooldown(self):
        """Immediately aborts if service is currently throttled under an active quota cooldown."""
        if self.is_quota_exhausted():
            remaining = self.get_remaining_cooldown_seconds()
            human = format_human_retry_delay(remaining)
            msg = get_friendly_quota_message(retry_after_human=human)
            logger.warning(f"Aborting Gemini call during active quota cooldown ({remaining:.1f}s remaining).")
            raise GeminiQuotaExceededError(
                message=msg,
                retry_delay_seconds=remaining,
                retry_after_human=human
            )

    def _handle_provider_error(self, e: Exception, operation: str) -> None:
        """
        Processes provider exceptions, detects quota errors, sets cooldown,
        and raises sanitized domain exceptions.
        """
        if is_gemini_quota_error(e):
            delay_sec, human = extract_gemini_retry_delay(e)
            cooldown = delay_sec if (delay_sec and delay_sec > 0) else 60.0
            self._quota_cooldown_until = time.time() + cooldown
            msg = get_friendly_quota_message(e, retry_after_human=human)
            quota_err = GeminiQuotaExceededError(
                message=msg,
                retry_delay_seconds=delay_sec,
                retry_after_human=human,
                original_error=e
            )
            self._last_quota_error = quota_err
            logger.warning(f"Gemini quota exhausted during {operation}. Cooldown active for {cooldown:.1f}s.")
            raise quota_err

        if is_gemini_transient_error(e):
            delay_sec, human = extract_gemini_retry_delay(e)
            msg = get_friendly_service_unavailable_message(e, retry_after_human=human)
            service_err = GeminiServiceUnavailableError(
                message=msg,
                retry_delay_seconds=delay_sec,
                retry_after_human=human,
                original_error=e
            )
            logger.warning(f"Gemini service unavailable during {operation}: {msg}")
            raise service_err

        sanitized = sanitize_error(e)
        logger.error(f"Gemini API error during {operation}: {sanitized}")
        raise RuntimeError(f"Gemini live {operation} failed: {sanitized}")

    def _execute_with_retry(
        self,
        operation: str,
        call_fn: Any,
        max_retries: int = 3,
        base_delay: float = 0.5,
        backoff_factor: float = 2.0,
        max_delay: float = 5.0
    ) -> Any:
        """
        Executes a Gemini API call with bounded exponential backoff and jitter
        for transient 503 errors only.
        - Immediately aborts if quota cooldown is active or quota 429 error occurs.
        - Immediately aborts on non-transient errors (e.g. 400, 401, 403).
        - Retries bounded up to max_retries with jitter.
        - On exhausting retries, raises GeminiServiceUnavailableError.
        """
        import random
        for attempt in range(max_retries + 1):
            self._check_quota_cooldown()
            try:
                return call_fn()
            except Exception as e:
                # Quota errors must never enter transient 503 retry loop
                if is_gemini_quota_error(e):
                    self._handle_provider_error(e, operation)

                # Non-transient errors must not be retried
                if not is_gemini_transient_error(e):
                    self._handle_provider_error(e, operation)

                # Transient 503 error
                if attempt < max_retries:
                    provider_delay, _ = extract_gemini_retry_delay(e)
                    if provider_delay is not None and provider_delay > 0:
                        delay = min(provider_delay, max_delay)
                    else:
                        delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                        jitter = random.uniform(0.05, 0.25)
                        delay = delay + jitter

                    logger.warning(
                        f"Transient Gemini {operation} error (attempt {attempt + 1}/{max_retries + 1}). "
                        f"Retrying in {delay:.2f}s: {sanitize_error(e)}"
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Gemini {operation} exhausted {max_retries} retries for transient 503: {sanitize_error(e)}"
                    )
                    self._handle_provider_error(e, operation)

    def test_connectivity(self) -> Dict[str, Any]:
        """
        Makes genuine test API calls to verify Gemini text generation and embeddings.
        Returns status dict without exposing credentials.
        """
        if not self.is_configured():
            return {
                "configured": False,
                "verified": False,
                "mode": "offline",
                "message": "GEMINI_API_KEY is not configured. Running in offline simulation mode."
            }

        if self.is_quota_exhausted():
            remaining = self.get_remaining_cooldown_seconds()
            human = format_human_retry_delay(remaining)
            msg = get_friendly_quota_message(retry_after_human=human)
            return {
                "configured": True,
                "verified": False,
                "mode": "quota_exceeded",
                "error": msg,
                "retry_after": human
            }

        try:
            from google.genai import types
            # 1. Test generation
            gen_res = self._client.models.generate_content(
                model=self.model_name,
                contents="ping",
                config=types.GenerateContentConfig(max_output_tokens=5, temperature=0.0)
            )
            # 2. Test embedding
            emb_res = self._client.models.embed_content(
                model=self.embedding_model_name,
                contents="ping",
                config=types.EmbedContentConfig(output_dimensionality=self.embedding_dimension)
            )
            emb_len = len(emb_res.embeddings[0].values) if hasattr(emb_res, "embeddings") and emb_res.embeddings else 0

            self._verified_live = True
            return {
                "configured": True,
                "verified": True,
                "mode": "live",
                "model": self.model_name,
                "embedding_model": self.embedding_model_name,
                "embedding_dimension": emb_len,
                "sample_generation": gen_res.text.strip() if gen_res.text else "OK"
            }
        except Exception as e:
            self._verified_live = False
            if is_gemini_quota_error(e):
                delay_sec, human = extract_gemini_retry_delay(e)
                cooldown = delay_sec if (delay_sec and delay_sec > 0) else 60.0
                self._quota_cooldown_until = time.time() + cooldown
                msg = get_friendly_quota_message(e, retry_after_human=human)
                logger.warning(f"Gemini connectivity verification hit quota limit: {msg}")
                return {
                    "configured": True,
                    "verified": False,
                    "mode": "quota_exceeded",
                    "error": msg,
                    "retry_after": human
                }
            sanitized = sanitize_error(e)
            logger.error(f"Gemini connectivity verification failed: {sanitized}")
            return {
                "configured": True,
                "verified": False,
                "mode": "error",
                "error": sanitized
            }

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        json_schema: Optional[type] = None,
        temperature: float = 0.2
    ) -> str:
        """
        Generate text or structured output from the configured AI provider.
        If AI_PROVIDER is set to groq or nvidia, dispatches to that active provider.
        In Gemini live mode: calls Gemini API with bounded exponential retry for 503 errors.
        On quota error: aborts immediately and raises GeminiQuotaExceededError.
        In offline mode: calls deterministic simulation generator.
        """
        raw_provider = getattr(settings, "AI_PROVIDER", "gemini")
        if isinstance(raw_provider, str) and raw_provider.strip().lower() not in ("gemini", "google", "google-genai"):
            from app.core.ai_provider import get_ai_provider
            active_p = get_ai_provider()
            return active_p.generate_text(
                prompt=prompt,
                system_instruction=system_instruction,
                json_schema=json_schema,
                temperature=temperature
            )

        if self.is_gemini_configured():
            from google.genai import types
            config_kwargs: Dict[str, Any] = {"temperature": temperature}
            if system_instruction:
                config_kwargs["system_instruction"] = system_instruction
            if json_schema:
                config_kwargs["response_mime_type"] = "application/json"
                config_kwargs["response_schema"] = json_schema

            gen_config = types.GenerateContentConfig(**config_kwargs)
            def _call():
                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=gen_config
                )
                return response.text or ""
            return self._execute_with_retry("generation", _call)

        # Deterministic offline response generator
        return self._fallback_generate(prompt, json_schema)

    def generate_multimodal_description(
        self,
        image_bytes: bytes,
        mime_type: str = "image/png",
        prompt: str = "Describe this educational diagram or formula in detail."
    ) -> str:
        """
        Multimodal visual analysis for textbook diagrams, formulas, and slide illustrations.
        In live mode: calls Gemini API with bounded exponential retry for 503 errors.
        On failure: raises sanitized domain exception (no silent fabrication in live mode).
        In offline mode: returns simulated diagram explanation.
        """
        if self.is_configured():
            from google.genai import types
            part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            def _call():
                response = self._client.models.generate_content(
                    model=self.multimodal_model_name,
                    contents=[part, prompt]
                )
                return response.text or ""
            return self._execute_with_retry("multimodal description", _call)

        return "Diagram illustrates educational concepts and structural relationships outlined in the course text."

    def get_embedding(self, text: str) -> List[float]:
        """
        Generate 768-dimensional dense semantic embedding.
        In live mode: calls Gemini API with bounded retry; raises domain error on persistent failure.
        In offline mode: uses deterministic pseudo-embedding.
        """
        if self.is_configured():
            from google.genai import types
            def _call():
                result = self._client.models.embed_content(
                    model=self.embedding_model_name,
                    contents=text,
                    config=types.EmbedContentConfig(output_dimensionality=self.embedding_dimension)
                )
                if hasattr(result, "embeddings") and len(result.embeddings) > 0:
                    vec = list(result.embeddings[0].values)
                elif hasattr(result, "embedding"):
                    vec = list(result.embedding.values)
                else:
                    raise ValueError("Gemini embed_content returned no embeddings")

                if len(vec) != self.embedding_dimension:
                    raise ValueError(f"Expected embedding dimension {self.embedding_dimension}, got {len(vec)}")
                return vec
            return self._execute_with_retry("embedding", _call)

        return self._pseudo_embedding(text)

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate dense semantic embeddings for a batch of texts.
        """
        if not texts:
            return []

        if self.is_configured():
            from google.genai import types
            def _call():
                result = self._client.models.embed_content(
                    model=self.embedding_model_name,
                    contents=texts,
                    config=types.EmbedContentConfig(output_dimensionality=self.embedding_dimension)
                )
                if hasattr(result, "embeddings") and len(result.embeddings) == len(texts):
                    vectors = [list(e.values) for e in result.embeddings]
                    for idx, v in enumerate(vectors):
                        if len(v) != self.embedding_dimension:
                            raise ValueError(f"Chunk {idx}: Expected dimension {self.embedding_dimension}, got {len(v)}")
                    return vectors
                else:
                    raise ValueError(f"Gemini embed_content count mismatch: expected {len(texts)}")
            return self._execute_with_retry("batch embedding", _call)

        return [self._pseudo_embedding(t) for t in texts]

    def _pseudo_embedding(self, text: str) -> List[float]:
        """
        Deterministic pseudo-embedding (768 dimensions) for offline simulation mode.
        """
        np.random.seed(abs(hash(text.lower())) % (2**32))
        vec = np.random.randn(self.embedding_dimension)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def _fallback_generate(self, prompt: str, json_schema: Optional[type] = None) -> str:
        """
        Fallback generator when Gemini API key is not configured (offline mode).
        Produces realistic structured JSON adhering to the target contracts.
        """
        p_lower = prompt.lower()
        if "assessment" in p_lower or "quiz" in p_lower:
            return json.dumps([
                {
                    "question_type": "mcq",
                    "prompt": "Based on the course materials, what is the primary role of the described concept?",
                    "options": [
                        "A) Standardizing feature representation across dimensions",
                        "B) Reducing dataset size by discarding variance",
                        "C) Increasing computational complexity of layers",
                        "D) Eliminating need for non-linear activations"
                    ],
                    "correct_answer": "A) Standardizing feature representation across dimensions",
                    "explanation": "As stated in the source text, standardizing inputs prevents gradient explosions and stabilizes training.",
                    "topic_name": "Fundamentals"
                }
            ])
        elif "misconception" in p_lower:
            return json.dumps({
                "misconception": "Confusing correlation with causation in feature representations.",
                "remediation_advice": "Review Section 2.1 focusing on experimental verification.",
                "topic_name": "Fundamentals"
            })
        elif "tutor" in p_lower or "grounded" in p_lower:
            if json_schema:
                return json.dumps({
                    "answer": "[Offline Simulation] Based on the provided lecture materials, the concept is explained in detail in the highlighted course excerpts.",
                    "is_sufficiently_grounded": True,
                    "cited_source_indices": [1],
                    "insufficient_evidence_reason": None
                })
            return "[Offline Simulation] Based on the provided lecture materials, the concept is explained in detail in the highlighted source sections."
        return "Explanation based on uploaded course material."

# Global singleton
gemini_service = GeminiService()
