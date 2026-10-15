"""NVIDIA HTTP adapter. Secret values and response error bodies never enter traces."""

import asyncio
import math
import re
import time
from typing import Any, Literal, Protocol

import httpx
from langchain_core.prompt_values import ChatPromptValue
from pydantic import BaseModel, Field, ValidationError

from workbench.config import ProviderSettings


class ProviderError(Exception):
    def __init__(self, code: str, message: str, raw_response: str | None = None):
        self.code = code
        self.raw_response = raw_response
        super().__init__(message)


def sanitize_model_text(value: str, limit: int = 24000) -> str:
    """Retain bounded model text, never reflected credentials or auth lines."""
    value = re.sub(r"nvapi-[A-Za-z0-9_-]+", "[REDACTED]", value)
    value = re.sub(r"(?i)bearer\s+[A-Za-z0-9_.-]+", "Bearer [REDACTED]", value)
    value = re.sub(r"(?im)^.*authorization.*$", "[REDACTED AUTHORIZATION]", value)
    return value.encode()[:limit].decode(errors="ignore")


class Provider(Protocol):
    chat_model: str
    embedding_model: str
    rerank_model: str
    calls: list[dict[str, Any]]

    async def embed(
        self, texts: list[str], input_type: Literal["query", "passage"]
    ) -> list[list[float]]: ...
    async def rerank(self, query: str, passages: list[str]) -> list[tuple[int, float]]: ...
    async def chat(self, prompt: ChatPromptValue) -> str: ...
    async def close(self) -> None: ...


class EmbeddingRow(BaseModel):
    index: int
    embedding: list[float] = Field(min_length=1, max_length=8192)


class NvidiaProvider:
    def __init__(self, config: ProviderSettings, transport: httpx.AsyncBaseTransport | None = None):
        self.config = config
        self.chat_model = config.chat_model
        self.embedding_model = config.embedding_model
        self.rerank_model = config.rerank_model
        self.calls: list[dict[str, Any]] = []
        key = config.nvidia_api_key
        if key is None or not key.get_secret_value().strip():
            raise ProviderError(
                "missing_credentials", "Configure NVIDIA_API_KEY in backend/.env to investigate."
            )
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {key.get_secret_value()}"},
            timeout=httpx.Timeout(config.provider_timeout_seconds, connect=10),
            transport=transport,
            follow_redirects=False,
        )
        self.output_budget_remaining: int | None = None
        self.requests = 0
        self.last_raw_response: str | None = None

    async def close(self) -> None:
        await self.client.aclose()

    async def request(self, workload: str, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(self.config.provider_retries + 1):
            if self.requests >= self.config.provider_max_requests:
                raise ProviderError(
                    "request_budget", "The investigation reached its provider request budget."
                )
            if self.output_budget_remaining is not None and workload == "chat":
                reserved = int(payload.get("max_tokens", 0))
                if reserved > self.output_budget_remaining:
                    raise ProviderError("output_budget", "Shared repair output budget exhausted.")
                # Reserve the maximum even for failed requests/retries; never reset per node.
                self.output_budget_remaining -= reserved
            self.requests += 1
            started = time.monotonic()
            record: dict[str, Any] = {
                "workload": workload,
                "model": payload["model"],
                "attempt": attempt + 1,
            }
            try:
                response = await self.client.post(url, json=payload)
                record["status"] = response.status_code
                if (
                    response.status_code in (429, 500, 502, 503, 504)
                    and attempt < self.config.provider_retries
                ):
                    await asyncio.sleep(0.4 * (attempt + 1))
                    continue
                if response.status_code != 200:
                    raise ProviderError(
                        "provider_http",
                        f"NVIDIA {workload} returned HTTP {response.status_code}. No "
                        f"substitute output was used.",
                    )
                if len(response.content) > 8_000_000:
                    raise ProviderError(
                        "invalid_provider_output",
                        "NVIDIA response exceeded the response size limit.",
                    )
                body = response.json()
                if not isinstance(body, dict):
                    raise ValueError("Response must be an object")
                usage = body.get("usage")
                if isinstance(usage, dict):
                    record["usage"] = {
                        k: v
                        for k, v in usage.items()
                        if k in ("prompt_tokens", "completion_tokens", "total_tokens")
                        and isinstance(v, int)
                    }
                return body
            except httpx.HTTPError as error:
                record["error"] = type(error).__name__
                if attempt == self.config.provider_retries:
                    raise ProviderError(
                        "provider_unavailable", f"NVIDIA {workload} request failed or timed out."
                    ) from None
                await asyncio.sleep(0.4 * (attempt + 1))
            except (ValueError, ValidationError):
                raise ProviderError(
                    "invalid_provider_output", "NVIDIA returned an invalid response envelope."
                ) from None
            finally:
                record["latency_ms"] = round((time.monotonic() - started) * 1000)
                self.calls.append(record)
        raise ProviderError("provider_unavailable", "NVIDIA request could not complete.")

    async def embed(
        self, texts: list[str], input_type: Literal["query", "passage"]
    ) -> list[list[float]]:
        if not texts or len(texts) > 24 or any(len(t.encode()) > 16000 for t in texts):
            raise ProviderError(
                "embedding_budget", "Embedding batch exceeds the supported input budget."
            )
        body = await self.request(
            "embedding",
            "https://integrate.api.nvidia.com/v1/embeddings",
            {
                "model": self.embedding_model,
                "input": texts,
                "input_type": input_type,
                "encoding_format": "float",
                "truncate": "NONE",
            },
        )
        try:
            rows = sorted(
                [EmbeddingRow.model_validate(row) for row in body["data"]],
                key=lambda row: row.index,
            )
            if [row.index for row in rows] != list(range(len(texts))):
                raise ValueError("Embedding cardinality mismatch")
            vectors = [row.embedding for row in rows]
            if len({len(v) for v in vectors}) != 1 or any(
                not math.isfinite(x) for v in vectors for x in v
            ):
                raise ValueError("Invalid embedding values")
            return vectors
        except (ValueError, KeyError, TypeError):
            raise ProviderError(
                "invalid_provider_output", "NVIDIA embedding response failed validation."
            ) from None

    async def rerank(self, query: str, passages: list[str]) -> list[tuple[int, float]]:
        body = await self.request(
            "rerank",
            self.config.rerank_url,
            {
                "model": self.rerank_model,
                "query": {"text": query},
                "passages": [{"text": text} for text in passages],
                "truncate": "NONE",
            },
        )
        try:
            result = [(int(row["index"]), float(row["logit"])) for row in body["rankings"]]
            if sorted(i for i, _ in result) != list(range(len(passages))) or any(
                not math.isfinite(score) for _, score in result
            ):
                raise ValueError("Invalid reranker permutation")
            return sorted(result, key=lambda row: (-row[1], row[0]))
        except (ValueError, KeyError, TypeError):
            raise ProviderError(
                "invalid_provider_output", "NVIDIA reranker response failed validation."
            ) from None

    async def chat(self, prompt: ChatPromptValue) -> str:
        self.last_raw_response = None
        messages = [
            {"role": "system" if m.type == "system" else "user", "content": str(m.content)}
            for m in prompt.to_messages()
        ]
        if sum(len(m["content"].encode()) for m in messages) > self.config.model_input_token_limit:
            raise ProviderError(
                "input_budget", "Prompt exceeds the conservative input token bound."
            )
        body = await self.request(
            "chat",
            "https://integrate.api.nvidia.com/v1/chat/completions",
            {
                "model": self.chat_model,
                "messages": messages,
                "temperature": 0,
                "max_tokens": self.config.model_output_token_limit,
                "response_format": {"type": "json_object"},
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
        try:
            choice = body["choices"][0]
            content = choice["message"]["content"]
            if isinstance(content, str):
                self.last_raw_response = sanitize_model_text(
                    content.replace(self.config.nvidia_api_key.get_secret_value(), "[REDACTED]")
                    if self.config.nvidia_api_key
                    else content
                )
            if (
                choice.get("finish_reason") != "stop"
                or not isinstance(content, str)
                or not content.strip()
            ):
                raise ValueError("Truncated or empty response")
            if len(content.encode()) > 24000:
                raise ValueError("Oversized response")
            return content
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError(
                "invalid_model_output",
                "NVIDIA chat output was empty, truncated, or invalid. No diagnosis was accepted.",
                self.last_raw_response,
            ) from None
