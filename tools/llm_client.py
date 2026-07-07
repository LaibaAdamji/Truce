# tools/llm_client.py

import time
import requests
from config.settings import settings
from db.operations import log_gemma_call

LLM_URL = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"


class GemmaCallError(Exception):
    """Raised when the LLM call fails outright."""
    pass


def call_gemma(
    agent_name: str,
    purpose: str,
    prompt: str,
    project_id: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> str:
    """
    Single choke point for every LLM call in the pipeline.

    agent_name:
        "client_agent" / "freelancer_agent" / "mediator_agent"

    purpose:
        "requirement_extraction" /
        "price_floor_reasoning" /
        "negotiation_move"

    Returns:
        Raw text response from the model.

    Raises:
        GemmaCallError on network failure, HTTP failure,
        malformed provider response, or empty response.
    """

    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": settings.LLM_MODEL_ID,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    start = time.monotonic()
    success = False
    content = ""

    try:
        resp = requests.post(
            LLM_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )

        print("Status:", resp.status_code)
        print(resp.text)

        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError:
            try:
                error_body = resp.json()
            except Exception:
                error_body = resp.text

            raise GemmaCallError(
                f"[{agent_name}/{purpose}] "
                f"LLM returned HTTP {resp.status_code}: {error_body}"
            )

        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            if not isinstance(content, str) or not content.strip():
                raise ValueError("Empty response")

        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise GemmaCallError(
                f"[{agent_name}/{purpose}] "
                f"Invalid response format from LLM: {e}"
            ) from e

        success = True
        return content

    except requests.exceptions.RequestException as e:
        raise GemmaCallError(
            f"[{agent_name}/{purpose}] Network failure: {e}"
        ) from e

    finally:
        latency_ms = int((time.monotonic() - start) * 1000)
        if project_id is not None:
            try:
                log_gemma_call(
                    {
                        "project_id": project_id,
                        "agent_name": agent_name,
                        "purpose": purpose,
                        "latency_ms": latency_ms,
                        "success": success,
                    }
                )
            except Exception as e:
                print(f"[WARN] Failed to log Gemma call: {e}")