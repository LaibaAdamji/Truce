# tools/llm_client.py

import sys
import time
import requests
from config.settings import settings
from db.operations import log_gemma_call

def _debug_print(message: str) -> None:
    sys.stdout.buffer.write(message.encode("utf-8", errors="replace") + b"\n")

class GemmaCallError(Exception):
    pass

def _log_llm_call(agent_name, purpose, project_id, start_time, success):
    latency_ms = int((time.monotonic() - start_time) * 1000)
    if project_id is not None:
        try:
            log_gemma_call({
                "project_id": project_id,
                "agent_name": agent_name,
                "purpose": purpose,
                "latency_ms": latency_ms,
                "success": success,
            })
        except Exception as e:
            print(f"[WARN] Failed to log Gemma call: {e}")

def _try_provider(url, api_key, model, prompt, temperature, max_tokens, label):
    """Returns content string on success, None on failure (never raises)."""
    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        _debug_print(f"[{label}] Status: {resp.status_code}")
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            if content and isinstance(content, str) and content.strip():
                return content
            _debug_print(f"[WARN] {label} returned empty content")
        else:
            _debug_print(f"[WARN] {label} HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        _debug_print(f"[WARN] {label} exception: {e}")
    return None

def call_gemma(
    agent_name: str,
    purpose: str,
    prompt: str,
    project_id: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> str:
    start_time = time.monotonic()
    # 1. Primary: Fireworks
    if settings.FIREWORKS_API_KEY:
        content = _try_provider(
            "https://api.fireworks.ai/inference/v1/chat/completions",
            settings.FIREWORKS_API_KEY,
            "accounts/fireworks/models/gpt-oss-20b",
            prompt, temperature, max_tokens, "Fireworks",
        )
        if content:
            _log_llm_call(agent_name, purpose, project_id, start_time, True)
            return content
    # 2. Fallback: existing Groq config (LLM_BASE_URL/LLM_API_KEY/LLM_MODEL_ID)
    if settings.LLM_API_KEY:
        content = _try_provider(
            f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions",
            settings.LLM_API_KEY,
            settings.LLM_MODEL_ID,
            prompt, temperature, max_tokens, "Groq",
        )
        if content:
            _log_llm_call(agent_name, purpose, project_id, start_time, True)
            return content
    # 3. Both failed
    _log_llm_call(agent_name, purpose, project_id, start_time, False)
    raise GemmaCallError(f"[{agent_name}/{purpose}] All LLM providers failed.")