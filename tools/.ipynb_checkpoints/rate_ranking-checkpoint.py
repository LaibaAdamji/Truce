"""
Local AMD-GPU rate ranking: scores a freelancer's proposed rate against
market comparables using Gemma running locally on the AMD pod.

Comparables are a static curated dataset (tools/data/comparables.json),
not live-scraped.
"""
import json
import re

from tools.market_research import get_comparables
from db import operations as db

_model = None
_tok = None


def _load_local_gemma():
    global _model, _tok
    if _model is None:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
        model_id = "google/gemma-2-2b-it"
        _tok = AutoTokenizer.from_pretrained(model_id)
        _model = AutoModelForCausalLM.from_pretrained(
            model_id, torch_dtype=torch.bfloat16, device_map="cuda"
        )
    return _model, _tok


def rank_rate(project_id: str, proposed_rate: float, skill: str) -> dict:
    """
    Returns {"score": int|None, "verdict": str, "reasoning": str}.
    Runs entirely on local AMD GPU inference (ROCm/PyTorch).
    """
    # Get comparables for this skill
    relevant = get_comparables(skill=skill, limit=5)

    model, tok = _load_local_gemma()
    
    prompt = (
        f"Proposed rate: ${proposed_rate}/hr for skill '{skill}'.\n"
        f"Market comparables: {json.dumps(relevant)}\n"
        "Score this rate 0-100 (100 = perfectly market-aligned) and give one-sentence reasoning. "
        'Respond as JSON: {"score": <int>, "verdict": <str>, "reasoning": <str>}'
    )
    
    batch = tok.apply_chat_template(
        [{"role": "user", "content": prompt}], 
        return_tensors="pt", 
        add_generation_prompt=True
    )
    inputs = batch.input_ids.to("cuda")  
    
    out = model.generate(inputs, max_new_tokens=150, temperature=0.2, do_sample=True)
    raw = tok.decode(out[0][inputs.shape[-1]:], skip_special_tokens=True).strip()
    
    return _parse_json_response(raw)


def _parse_json_response(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"```json\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return {"score": None, "verdict": "unparseable", "reasoning": raw}