from tools.llm_client import call_gemma

try:
    response = call_gemma(
        agent_name="test",
        purpose="smoke_test",
        prompt="Say hello in one sentence."
    )

    print("\n=== LLM RESPONSE ===")
    print(response)

except Exception as e:
    print("\n=== ERROR ===")
    print(type(e).__name__)
    print(e)