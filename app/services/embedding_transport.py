"""Fixed-origin embedding HTTP; no SDK retries, source logging or file uploads."""
import asyncio
from array import array
import json
import math
import httpx

MODEL = "text-embedding-3-small"
DIMENSIONS = 1536
CONFIG = "small1536-body-v1-bytes-reservation-20k-micro-per-million"


class EmbeddingError(Exception):
    """Safe public code only."""


def input_bound(inputs: list[str], *, query: bool = False) -> int:
    if not 1 <= len(inputs) <= 16 or (query and len(inputs) != 1):
        raise EmbeddingError("INPUT_LIMIT")
    sizes = [len(value.encode("utf-8")) for value in inputs]
    if any(not value.strip() for value in inputs) or any(n > (2048 if query else 8000) for n in sizes):
        raise EmbeddingError("INPUT_LIMIT")
    if sum(sizes) > 16000 or (query and len(inputs[0]) > 256):
        raise EmbeddingError("INPUT_LIMIT")
    return sum(sizes)


def cost_micro(tokens: int) -> int:
    return (tokens + 49) // 50


def validate_response(value, count: int, upper: int):
    try:
        if value["model"] != MODEL or len(value["data"]) != count:
            raise ValueError()
        usage = value["usage"]
        tokens = usage["total_tokens"]
        if type(tokens) is not int or not 0 < tokens <= upper or usage["prompt_tokens"] != tokens:
            raise ValueError()
        vectors = [None] * count
        for item in value["data"]:
            index, raw = item["index"], item["embedding"]
            if type(index) is not int or not 0 <= index < count or vectors[index] is not None or len(raw) != DIMENSIONS:
                raise ValueError()
            if any(type(v) not in {int, float} or not math.isfinite(v) for v in raw) or not any(raw):
                raise ValueError()
            vector = array("f", raw)
            if any(not math.isfinite(v) for v in vector) or not any(vector):
                raise ValueError()
            vectors[index] = vector
        return vectors, tokens
    except (KeyError, TypeError, ValueError, OverflowError):
        raise EmbeddingError("INVALID_PROVIDER_RESPONSE") from None


async def request_embeddings(inputs, key):
    try:
        async with asyncio.timeout(10):
            async with httpx.AsyncClient(timeout=httpx.Timeout(8, connect=2), trust_env=False,
                                         follow_redirects=False) as client:
                async with client.stream("POST", "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": "Bearer " + key},
                    json={"model": MODEL, "dimensions": DIMENSIONS, "encoding_format": "float", "input": inputs}) as response:
                    if response.status_code != 200:
                        raise EmbeddingError("PROVIDER_REJECTED")
                    chunks, size = [], 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > 2 * 1024 * 1024:
                            raise EmbeddingError("PROVIDER_RESPONSE_LIMIT")
                        chunks.append(chunk)
                    return json.loads(b"".join(chunks))
    except (TimeoutError, httpx.HTTPError):
        raise EmbeddingError("PROVIDER_TIMEOUT_OR_NETWORK") from None
    except (ValueError, UnicodeError):
        raise EmbeddingError("INVALID_PROVIDER_RESPONSE") from None
