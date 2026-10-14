import os
import re
import json
import time
import logging
import random
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple, Type
import httpx

from app.core.config import settings
from app.core.gemini import (
    GeminiQuotaExceededError,
    GeminiServiceUnavailableError,
    is_gemini_quota_error,
    is_gemini_transient_error,
    extract_gemini_retry_delay,
    format_human_retry_delay,
    get_friendly_quota_message,
    get_friendly_service_unavailable_message,
    gemini_service,
)

logger = logging.getLogger(__name__)

# ==============================================================================
# Domain Exceptions (Unified & Backwards-Compatible)
# ==============================================================================
class AIProviderError(RuntimeError):
    """Base exception for all AI provider operations."""
    def __init__(self, message: str, provider: Optional[str] = None, original_error: Optional[Exception] = None):
        self.message = message
        self.provider = provider
        self.original_error = original_error
        super().__init__(self.message)

class AIAuthError(AIProviderError):
    """Raised when authentication fails (HTTP 401 or invalid API key)."""
    def __init__(self, message: str, provider: Optional[str] = None, original_error: Optional[Exception] = None):
        super().__init__(message, provider=provider, original_error=original_error)

class AIQuotaExceededError(GeminiQuotaExceededError, AIProviderError):
    """
    Raised when provider rate limit or quota is exhausted (HTTP 429).
    Subclasses GeminiQuotaExceededError for transparent compatibility with existing catch blocks.
    """
    def __init__(
        self,
        message: Optional[str] = None,
        retry_delay_seconds: Optional[float] = None,
        retry_after_human: Optional[str] = None,
        provider: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        base_msg = "Live AI generation is temporarily unavailable because the AI service has reached its current usage limit. Please try again later."
        if message and "temporarily unavailable" in message.lower():
            final_msg = message
        elif retry_after_human:
            final_msg = f"{base_msg} (estimated retry {retry_after_human})."
        else:
            final_msg = base_msg

        GeminiQuotaExceededError.__init__(
            self,
            message=final_msg,
            retry_delay_seconds=retry_delay_seconds,
            retry_after_human=retry_after_human,
            original_error=original_error
        )
        AIProviderError.__init__(self, message=final_msg, provider=provider, original_error=original_error)

class AIServiceUnavailableError(GeminiServiceUnavailableError, AIProviderError):
    """
    Raised when provider encounters transient service unavailability (HTTP 503/502/504 or overload)
    after exhausting retries.
    Subclasses GeminiServiceUnavailableError for transparent compatibility with existing catch blocks.
    """
    def __init__(
        self,
        message: Optional[str] = None,
        retry_delay_seconds: Optional[float] = None,
        retry_after_human: Optional[str] = None,
        provider: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        base_msg = "Live AI generation is temporarily unavailable due to high model demand. Please try again in a few moments."
        if message and "temporarily unavailable" in message.lower():
            final_msg = message
        elif retry_after_human:
            final_msg = f"{base_msg} (estimated retry {retry_after_human})."
        else:
            final_msg = base_msg

        GeminiServiceUnavailableError.__init__(
            self,
            message=final_msg,
            retry_delay_seconds=retry_delay_seconds,
            retry_after_human=retry_after_human,
            original_error=original_error
        )
        AIProviderError.__init__(self, message=final_msg, provider=provider, original_error=original_error)

class UnsupportedCapabilityError(AIProviderError):
    """Raised when an operation (e.g. multimodal description or embeddings) is called on an unsupported provider."""
    def __init__(self, message: str, provider: Optional[str] = None, capability: Optional[str] = None):
        self.capability = capability
        super().__init__(message, provider=provider)

class AIOutputParsingError(AIProviderError):
    """Raised when the model response fails structured validation or JSON parsing."""
    def __init__(self, message: str, raw_output: str, provider: Optional[str] = None):
        self.raw_output = raw_output
        super().__init__(message, provider=provider)


# ==============================================================================
# Error Sanitization & Detection
# ==============================================================================
def sanitize_ai_error(err: Exception) -> str:
    """
    Sanitize error message to prevent exposure of API keys, Authorization headers,
    raw provider exception objects, or internal URLs.
    """
    msg = str(err)

    # Redact known configured keys
    for key_attr in ["GEMINI_API_KEY", "GROQ_API_KEY", "NVIDIA_API_KEY"]:
        val = getattr(settings, key_attr, None)
        if isinstance(val, str) and val:
            msg = msg.replace(val, "[REDACTED_API_KEY]")
        env_val = os.environ.get(key_attr)
        if isinstance(env_val, str) and env_val:
            msg = msg.replace(env_val, "[REDACTED_API_KEY]")

    # Redact provider key patterns
    msg = re.sub(r'AIza[0-9A-Za-z-_]{35}', '[REDACTED_API_KEY]', msg)
    msg = re.sub(r'gsk_[A-Za-z0-9_-]{20,}', '[REDACTED_API_KEY]', msg)
    msg = re.sub(r'nvapi-[A-Za-z0-9_-]{20,}', '[REDACTED_API_KEY]', msg)
    msg = re.sub(r'Bearer\s+[A-Za-z0-9_\-]+', 'Bearer [REDACTED]', msg)
    msg = re.sub(r'key=[A-Za-z0-9_\-]+', 'key=[REDACTED]', msg)

    # Scrub endpoints and internal URLs
    msg = re.sub(r'https?://[^\s\'"]+', '[API_ENDPOINT]', msg)

    return msg

def is_ai_quota_error(err: Exception) -> bool:
    """Detects quota and rate-limit errors across Gemini, Groq, and NVIDIA."""
    if isinstance(err, (AIQuotaExceededError, GeminiQuotaExceededError)):
        return True

    status_code = getattr(err, "status_code", None) or getattr(getattr(err, "response", None), "status_code", None)
    if status_code == 429:
        return True

    err_str = str(err).lower()
    quota_signatures = [
        "resource_exhausted",
        "quota exceeded",
        "rate limit",
        "rate_limit",
        "too many requests",
        "tokens per minute",
        "requests per minute",
        "rpm",
        "tpm",
        "429"
    ]
    return any(sig in err_str for sig in quota_signatures)

def is_ai_transient_error(err: Exception) -> bool:
    """
    Detects transient overload errors across all providers (503, 502, 504).
    429 quota errors are strictly excluded.
    """
    if is_ai_quota_error(err):
        return False

    if isinstance(err, (AIServiceUnavailableError, GeminiServiceUnavailableError)):
        return True

    status_code = getattr(err, "status_code", None) or getattr(getattr(err, "response", None), "status_code", None)
    if status_code in (502, 503, 504):
        return True

    err_str = str(err).lower()
    transient_signatures = [
        "503", "service unavailable", "service_unavailable",
        "high demand", "overloaded", "model is overloaded",
        "temporarily overloaded", "bad gateway", "gateway timeout"
    ]
    return any(sig in err_str for sig in transient_signatures)

def is_ai_auth_error(err: Exception) -> bool:
    """Detects authentication / invalid API key errors (HTTP 401, 403)."""
    if isinstance(err, AIAuthError):
        return True

    status_code = getattr(err, "status_code", None) or getattr(getattr(err, "response", None), "status_code", None)
    if status_code in (401, 403):
        return True

    err_str = str(err).lower()
    auth_signatures = ["invalid_api_key", "invalid api key", "unauthorized", "authentication failed", "forbidden"]
    return any(sig in err_str for sig in auth_signatures)


# ==============================================================================
# Base Provider Interface
# ==============================================================================
class BaseAIProvider(ABC):
    """Abstract base provider for LearnMate AI generation."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Returns a dictionary of supported capabilities:
        - text_generation: bool
        - structured_output: bool
        - multimodal_image: bool
        - multimodal_video: bool
        - embeddings: bool
        """
        pass

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        json_schema: Optional[type] = None,
        temperature: float = 0.2
    ) -> str:
        pass

    @abstractmethod
    def generate_multimodal_description(
        self,
        image_bytes: bytes,
        mime_type: str = "image/png",
        prompt: str = "Describe this educational diagram or formula in detail."
    ) -> str:
        pass

    @abstractmethod
    def get_embedding(self, text: str) -> List[float]:
        pass

    @abstractmethod
    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        pass

    @abstractmethod
    def test_connectivity(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def is_quota_exhausted(self) -> bool:
        pass

    @abstractmethod
    def get_remaining_cooldown_seconds(self) -> float:
        pass

    @abstractmethod
    def reset_quota_cooldown(self) -> None:
        pass


# ==============================================================================
# Provider Implementation 1: Google Gemini
# ==============================================================================
class GeminiProvider(BaseAIProvider):
    """Google Gemini provider integrating the official google-genai SDK."""

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return gemini_service.model_name

    def is_configured(self) -> bool:
        return gemini_service.is_configured()

    def get_capabilities(self) -> Dict[str, bool]:
        return {
            "text_generation": True,
            "structured_output": True,
            "multimodal_image": True,
            "multimodal_video": True,
            "embeddings": True
        }

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        json_schema: Optional[type] = None,
        temperature: float = 0.2
    ) -> str:
        # Directly call GeminiService internal live/fallback logic without infinite recursion
        if gemini_service.is_configured():
            from google.genai import types
            config_kwargs: Dict[str, Any] = {"temperature": temperature}
            if system_instruction:
                config_kwargs["system_instruction"] = system_instruction
            if json_schema:
                config_kwargs["response_mime_type"] = "application/json"
                config_kwargs["response_schema"] = json_schema

            gen_config = types.GenerateContentConfig(**config_kwargs)
            def _call():
                response = gemini_service._client.models.generate_content(
                    model=gemini_service.model_name,
                    contents=prompt,
                    config=gen_config
                )
                return response.text or ""
            return gemini_service._execute_with_retry("generation", _call)

        return gemini_service._fallback_generate(prompt, json_schema)

    def generate_multimodal_description(
        self,
        image_bytes: bytes,
        mime_type: str = "image/png",
        prompt: str = "Describe this educational diagram or formula in detail."
    ) -> str:
        return gemini_service.generate_multimodal_description(image_bytes, mime_type, prompt)

    def get_embedding(self, text: str) -> List[float]:
        return gemini_service.get_embedding(text)

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        return gemini_service.get_embeddings_batch(texts)

    def test_connectivity(self) -> Dict[str, Any]:
        res = gemini_service.test_connectivity()
        res["provider"] = "gemini"
        return res

    def is_quota_exhausted(self) -> bool:
        return gemini_service.is_quota_exhausted()

    def get_remaining_cooldown_seconds(self) -> float:
        return gemini_service.get_remaining_cooldown_seconds()

    def reset_quota_cooldown(self) -> None:
        gemini_service.reset_quota_cooldown()


# ==============================================================================
# Base OpenAI-Compatible Provider (Groq and NVIDIA)
# ==============================================================================
class OpenAICompatibleProvider(BaseAIProvider):
    """
    Base implementation for providers exposing documented OpenAI-compatible endpoints:
    - GroqCloud (https://api.groq.com/openai/v1)
    - NVIDIA Nemotron / NIM (https://integrate.api.nvidia.com/v1)
    """
    def __init__(
        self,
        name: str,
        api_key: Optional[str],
        base_url: str,
        model_name: str,
        timeout_seconds: float = 30.0
    ):
        self._name = name
        self._api_key = api_key or os.environ.get(f"{name.upper()}_API_KEY")
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self._quota_cooldown_until: Optional[float] = None

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def model_name(self) -> str:
        return self._model_name

    def is_configured(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    def is_quota_exhausted(self) -> bool:
        return self._quota_cooldown_until is not None and time.time() < self._quota_cooldown_until

    def get_remaining_cooldown_seconds(self) -> float:
        if not self.is_quota_exhausted():
            return 0.0
        return max(0.0, (self._quota_cooldown_until or 0.0) - time.time())

    def reset_quota_cooldown(self) -> None:
        self._quota_cooldown_until = None

    def get_capabilities(self) -> Dict[str, bool]:
        return {
            "text_generation": True,
            "structured_output": True,
            "multimodal_image": False,
            "multimodal_video": False,
            "embeddings": False
        }

    def _strip_markdown_code_fences(self, text: str) -> str:
        """Strips surrounding ```json ... ``` code fences from model outputs."""
        clean = text.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
            clean = re.sub(r"\s*```$", "", clean)
        return clean.strip()

    def _build_schema_instruction(self, json_schema: type) -> str:
        """Extracts JSON schema representation to enforce structured model output."""
        try:
            if hasattr(json_schema, "model_json_schema"):
                schema_dict = json_schema.model_json_schema()
                properties = schema_dict.get("properties", {})
                req = schema_dict.get("required", [])
                return (
                    f"CRITICAL: You MUST respond ONLY with valid, RFC 8259 JSON adhering strictly to this schema: "
                    f"{json.dumps({'type': 'object', 'properties': properties, 'required': req})}. "
                    f"Do not include any introductory remarks, markdown backticks, or concluding thoughts."
                )
        except Exception:
            pass
        return "CRITICAL: You MUST respond with valid JSON matching the requested structure. Do not use code blocks."

    def _execute_chat_completion_with_retry(
        self,
        payload: Dict[str, Any],
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 4.0
    ) -> str:
        """
        Executes chat completion with bounded exponential retry ONLY for transient 503/502/504 errors.
        Immediately aborts on 429 quota exhaustion and 401 auth failures.
        """
        if not self.is_configured():
            raise AIAuthError(
                f"{self.provider_name.upper()} API key not configured. Please set {self.provider_name.upper()}_API_KEY.",
                provider=self.provider_name
            )

        if self.is_quota_exhausted():
            rem = self.get_remaining_cooldown_seconds()
            human = format_human_retry_delay(rem)
            msg = get_friendly_quota_message(retry_after_human=human)
            logger.warning(f"Aborting {self.provider_name} call during active quota cooldown ({rem:.1f}s remaining).")
            raise AIQuotaExceededError(
                message=msg,
                retry_delay_seconds=rem,
                retry_after_human=human,
                provider=self.provider_name
            )

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }
        url = f"{self._base_url}/chat/completions"

        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(timeout=self._timeout_seconds) as client:
                    resp = client.post(url, headers=headers, json=payload)

                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices and "message" in choices[0]:
                        raw_content = choices[0]["message"].get("content", "")
                        return self._strip_markdown_code_fences(raw_content)
                    raise AIOutputParsingError(f"{self.provider_name} returned empty completion choices.", raw_output=resp.text, provider=self.provider_name)

                # HTTP 401 / 403: Authentication failure (never retry)
                if resp.status_code in (401, 403):
                    clean_err = sanitize_ai_error(Exception(resp.text))
                    logger.error(f"{self.provider_name} authentication failed: {clean_err}")
                    raise AIAuthError(
                        f"Authentication failed for {self.provider_name.upper()}: Invalid API key or unauthorized.",
                        provider=self.provider_name,
                        original_error=Exception(resp.text)
                    )

                # HTTP 429: Quota / Rate Limit (never enter 503 retry loop)
                if resp.status_code == 429 or is_ai_quota_error(Exception(resp.text)):
                    retry_header = resp.headers.get("retry-after")
                    delay_sec = float(retry_header) if (retry_header and retry_header.isdigit()) else None
                    cooldown = delay_sec if (delay_sec and delay_sec > 0) else 60.0
                    self._quota_cooldown_until = time.time() + cooldown
                    human_delay = format_human_retry_delay(cooldown)
                    msg = get_friendly_quota_message(retry_after_human=human_delay)
                    logger.warning(f"{self.provider_name} rate limit or quota exceeded: {msg}. Cooldown active for {cooldown:.1f}s.")
                    raise AIQuotaExceededError(
                        message=msg,
                        retry_delay_seconds=delay_sec,
                        retry_after_human=human_delay,
                        provider=self.provider_name,
                        original_error=Exception(resp.text)
                    )

                # HTTP 502/503/504: Transient service unavailability
                if resp.status_code in (502, 503, 504) or is_ai_transient_error(Exception(resp.text)):
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt) + random.uniform(0.05, 0.25), max_delay)
                        logger.warning(
                            f"Transient {self.provider_name} HTTP {resp.status_code} error (attempt {attempt + 1}/{max_retries + 1}). "
                            f"Retrying in {delay:.2f}s..."
                        )
                        time.sleep(delay)
                        continue
                    else:
                        msg = get_friendly_service_unavailable_message()
                        logger.error(f"{self.provider_name} exhausted retries for transient HTTP {resp.status_code}: {msg}")
                        raise AIServiceUnavailableError(message=msg, provider=self.provider_name, original_error=Exception(resp.text))

                # Other HTTP errors
                clean_err = sanitize_ai_error(Exception(resp.text))
                logger.error(f"{self.provider_name} returned unhandled HTTP {resp.status_code}: {clean_err}")
                raise AIProviderError(f"{self.provider_name.upper()} API error (HTTP {resp.status_code}): {clean_err}", provider=self.provider_name)

            except (AIAuthError, AIQuotaExceededError, AIServiceUnavailableError):
                raise
            except httpx.RequestError as req_err:
                # Network or connection error: retry if transient
                if attempt < max_retries:
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0.05, 0.25), max_delay)
                    logger.warning(f"Connection issue contacting {self.provider_name} ({req_err}). Retrying in {delay:.2f}s...")
                    time.sleep(delay)
                else:
                    msg = get_friendly_service_unavailable_message()
                    logger.error(f"{self.provider_name} connection failed after retries: {sanitize_ai_error(req_err)}")
                    raise AIServiceUnavailableError(message=msg, provider=self.provider_name, original_error=req_err)

        raise AIServiceUnavailableError(message=get_friendly_service_unavailable_message(), provider=self.provider_name)

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        json_schema: Optional[type] = None,
        temperature: float = 0.2
    ) -> str:
        if not self.is_configured():
            return gemini_service._fallback_generate(prompt, json_schema)

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature
        }

        if json_schema:
            payload["response_format"] = {"type": "json_object"}
            schema_inst = self._build_schema_instruction(json_schema)
            if messages and messages[0]["role"] == "system":
                messages[0]["content"] += f"\n\n{schema_inst}"
            else:
                messages.insert(0, {"role": "system", "content": schema_inst})

        return self._execute_chat_completion_with_retry(payload)

    def generate_multimodal_description(
        self,
        image_bytes: bytes,
        mime_type: str = "image/png",
        prompt: str = "Describe this educational diagram or formula in detail."
    ) -> str:
        raise UnsupportedCapabilityError(
            f"Provider '{self.provider_name}' does not support multimodal image analysis. "
            f"Please configure Gemini (gemini-3.8-flash) or a vision-capable provider for multimodal document processing.",
            provider=self.provider_name,
            capability="multimodal_image"
        )

    def get_embedding(self, text: str) -> List[float]:
        raise UnsupportedCapabilityError(
            f"Provider '{self.provider_name}' does not support generating compatible 768-dimensional embeddings. "
            f"LearnMate AI's vector index requires Gemini embeddings (gemini-embedding-001) or existing indexed vectors.",
            provider=self.provider_name,
            capability="embeddings"
        )

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        raise UnsupportedCapabilityError(
            f"Provider '{self.provider_name}' does not support dense embeddings. "
            f"LearnMate AI's vector index requires Gemini embeddings (gemini-embedding-001) or existing indexed vectors.",
            provider=self.provider_name,
            capability="embeddings"
        )

    def test_connectivity(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "provider": self.provider_name,
                "configured": False,
                "verified": False,
                "mode": "offline",
                "message": f"{self.provider_name.upper()}_API_KEY is not configured."
            }

        try:
            sample = self.generate_text("Reply with 'OK'", temperature=0.0)
            return {
                "provider": self.provider_name,
                "configured": True,
                "verified": True,
                "mode": "live",
                "model": self.model_name,
                "sample_generation": sample[:50]
            }
        except Exception as e:
            return {
                "provider": self.provider_name,
                "configured": True,
                "verified": False,
                "mode": "error",
                "error": sanitize_ai_error(e)
            }


# ==============================================================================
# Provider Implementation 2: GroqCloud
# ==============================================================================
class GroqProvider(OpenAICompatibleProvider):
    """
    GroqCloud high-throughput inference provider.
    Uses official OpenAI-compatible chat completions interface at https://api.groq.com/openai/v1.
    Default model: llama-3.3-70b-versatile (or llama-3.1-8b-instant).
    """
    def __init__(self):
        super().__init__(
            name="groq",
            api_key=settings.GROQ_API_KEY,
            base_url=getattr(settings, "GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            model_name=getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile"),
            timeout_seconds=30.0
        )


# ==============================================================================
# Provider Implementation 3: NVIDIA Nemotron
# ==============================================================================
class NvidiaNemotronProvider(OpenAICompatibleProvider):
    """
    NVIDIA Nemotron / NIM inference provider.
    Uses official OpenAI-compatible chat completions interface at https://integrate.api.nvidia.com/v1.
    Default model: nvidia/llama-3.1-nemotron-70b-instruct (or nvidia/nemotron-4-340b-instruct).
    """
    def __init__(self):
        super().__init__(
            name="nvidia",
            api_key=settings.NVIDIA_API_KEY,
            base_url=getattr(settings, "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
            model_name=getattr(settings, "NVIDIA_MODEL", "nvidia/llama-3.1-nemotron-70b-instruct"),
            timeout_seconds=45.0
        )


# ==============================================================================
# Factory & Multi-Provider Registry
# ==============================================================================
_PROVIDERS_CACHE: Dict[str, BaseAIProvider] = {}

def get_ai_provider(provider_name: Optional[str] = None) -> BaseAIProvider:
    """
    Factory function to retrieve or instantiate the configured AI provider.
    Validates provider names against supported list: 'gemini', 'groq', 'nvidia'.
    """
    raw = provider_name if provider_name is not None else getattr(settings, "AI_PROVIDER", "gemini")
    raw_name = (raw if isinstance(raw, str) else "gemini").strip().lower()

    if raw_name in ("google", "gemini", "google-genai"):
        norm_name = "gemini"
    elif raw_name in ("groq", "groqcloud"):
        norm_name = "groq"
    elif raw_name in ("nvidia", "nemotron", "nvidia-nemotron", "nim"):
        norm_name = "nvidia"
    else:
        raise ValueError(
            f"Unsupported AI_PROVIDER '{raw}'. "
            f"Supported providers are: 'gemini', 'groq', 'nvidia'."
        )

    if norm_name not in _PROVIDERS_CACHE:
        if norm_name == "gemini":
            _PROVIDERS_CACHE[norm_name] = GeminiProvider()
        elif norm_name == "groq":
            _PROVIDERS_CACHE[norm_name] = GroqProvider()
        elif norm_name == "nvidia":
            _PROVIDERS_CACHE[norm_name] = NvidiaNemotronProvider()

    return _PROVIDERS_CACHE[norm_name]

def reset_provider_cache():
    """Resets provider instances (useful when switching settings dynamically during tests)."""
    _PROVIDERS_CACHE.clear()


# ==============================================================================
# Unified AI Service Proxy
# ==============================================================================
class UnifiedAIService:
    """
    Unified AI proxy routing requests to the configured provider:
    - Text generation & structured output -> active provider (Gemini, Groq, NVIDIA)
    - Embeddings -> locked to Gemini (gemini-embedding-001) to protect index integrity
    - Multimodal operations -> checked against provider capabilities
    """
    @property
    def active_provider_name(self) -> str:
        return get_ai_provider().provider_name

    @property
    def active_model_name(self) -> str:
        return get_ai_provider().model_name

    def is_configured(self) -> bool:
        return get_ai_provider().is_configured()

    def get_capabilities(self) -> Dict[str, bool]:
        return get_ai_provider().get_capabilities()

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        json_schema: Optional[type] = None,
        temperature: float = 0.2
    ) -> str:
        return get_ai_provider().generate_text(
            prompt=prompt,
            system_instruction=system_instruction,
            json_schema=json_schema,
            temperature=temperature
        )

    def generate_multimodal_description(
        self,
        image_bytes: bytes,
        mime_type: str = "image/png",
        prompt: str = "Describe this educational diagram or formula in detail."
    ) -> str:
        provider = get_ai_provider()
        caps = provider.get_capabilities()
        if not caps.get("multimodal_image", False):
            # If current text provider doesn't support multimodal, check if Gemini is configured as fallback
            if gemini_service.is_gemini_configured():
                logger.info(f"Active provider '{provider.provider_name}' lacks multimodal support; routing image extraction to Gemini.")
                return gemini_service.generate_multimodal_description(image_bytes, mime_type, prompt)
            raise UnsupportedCapabilityError(
                f"Active provider '{provider.provider_name}' does not support multimodal image analysis. "
                f"Multimodal operations require GEMINI_API_KEY with gemini-3.8-flash.",
                provider=provider.provider_name,
                capability="multimodal_image"
            )
        return provider.generate_multimodal_description(image_bytes, mime_type, prompt)

    def get_embedding(self, text: str) -> List[float]:
        """
        Embeddings are strictly preserved in Gemini's 768-dimensional space
        to prevent vector space corruption (Phase 4 requirement).
        """
        return gemini_service.get_embedding(text)

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        return gemini_service.get_embeddings_batch(texts)

    def is_quota_exhausted(self) -> bool:
        return get_ai_provider().is_quota_exhausted()

    def get_remaining_cooldown_seconds(self) -> float:
        return get_ai_provider().get_remaining_cooldown_seconds()

    def reset_quota_cooldown(self) -> None:
        get_ai_provider().reset_quota_cooldown()

    def test_connectivity(self) -> Dict[str, Any]:
        return get_ai_provider().test_connectivity()

# Global Unified AI Service singleton
ai_service = UnifiedAIService()
