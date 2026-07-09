"""
tests/test_mediator_agent.py

Smoke test for the Mediator Agent.

Pipeline:

Project
    ↓
Requirement (budget)
    ↓
Price Floor
    ↓
Negotiation
    ↓
Negotiation Rounds
"""

from agents.mediator_agent import run_negotiation
from db import operations as db

CLIENT_PROFILE_ID = "72531437-5384-4aee-8734-38898c2f9547"


def divider(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main():

    divider("STEP 1 — CREATE PROJECT")

    result = db.save_project(
        {
            "client_profile_id": CLIENT_PROFILE_ID,
            "title": "Mediator Smoke Test",
            "description": "Need a React dashboard.",
            "status": "draft",
        }
    )

    project = result["project"]
    version = result["version"]

    project_id = str(project["project_id"])
    version_id = str(version["version_id"])

    print("Project:", project_id)
    print("Version:", version_id)

    divider("STEP 2 — INSERT CLIENT BUDGET")

    db.save_requirement(
        {
            "version_id": version_id,
            "type": "budget",
            "value": "$80/hr",
            "timeline": None,
            "budget_hint": 80,
            "confidence": 1.0,
        }
    )

    print("✓ Budget requirement inserted")

    divider("STEP 3 — INSERT PRICE FLOOR")

    db.save_price_floor(
        {
            "version_id": version_id,
            "amount": 60,
            "reasoning": "Market research indicates $60/hr is fair.",
            "confidence": 0.95,
        }
    )

    print("✓ Price floor inserted")

    divider("STEP 4 — RUN NEGOTIATION")

    state = run_negotiation(
        project_id=project_id,
        version_id=version_id,
    )

    print()

    print("Negotiation Status :", state.status)
    print("Floor              :", state.floor)
    print("Ceiling            :", state.ceiling)
    print("Current Offer      :", state.current_offer)
    print("Rounds             :", state.round_count)

    divider("STEP 5 — VERIFY DATABASE")

    rounds = db.get_negotiation_rounds(
        str(state.negotiation_id)
    )

    print(f"{len(rounds)} round(s) saved.\n")

    for r in rounds:

        print(
            f"""
Round {r['round_number']}

Offer:
${r['offer']}/hr

Message:
{r['message']}
"""
        )

    divider("DONE")

    print("✓ Mediator Agent smoke test PASSED")


if __name__ == "__main__":
    main()