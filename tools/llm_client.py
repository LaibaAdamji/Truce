# tools/llm_client.py
import time
import requests
from config.settings import settings
from db.operations import log_gemma_call

FIREWORKS_URL = "https://api.fireworks.ai/inference/v1/chat/completions"


class GemmaCallError(Exception):
    """Raised when the Fireworks/Gemma call fails outright."""
    pass


def call_gemma(agent_name: str, purpose: str, prompt: str, project_id: str | None = None,
                temperature: float = 0.3, max_tokens: int = 1024) -> str:
    """
    Single choke point for every Gemma call in the pipeline.
    agent_name: "client_agent" / "freelancer_agent" / "mediator_agent"
    purpose: "requirement_extraction" / "price_floor_reasoning" / "negotiation_move"
    Returns: raw text content from the model.
    Raises: GemmaCallError on network failure, non-200, or empty response.
    """
    headers = {
        "Authorization": f"Bearer {settings.FIREWORKS_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.FIREWORKS_MODEL_ID,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    start = time.monotonic()
    success = False
    content = ""

    try:
        resp = requests.post(FIREWORKS_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        if not content or not content.strip():
            raise GemmaCallError(f"[{agent_name}/{purpose}] Empty response from Gemma")
        success = True
        return content

    except requests.exceptions.RequestException as e:
        raise GemmaCallError(f"[{agent_name}/{purpose}] Fireworks call failed: {e}") from e

    finally:
        latency_ms = int((time.monotonic() - start) * 1000)
        try:
            log_gemma_call(
                project_id=project_id,
                agent_name=agent_name,
                purpose=purpose,
                latency_ms=latency_ms,
                success=success,
            )
        except Exception:
            pass  # never let logging failure crash the actual call