"""
tests/test_pipeline.py

End-to-end smoke test.

Flow

Client Brief
    ↓
Client Agent
    ↓
Freelancer Agent
    ↓
Mediator Agent
    ↓
Database verification
"""

from agents.client_agent import (
    create_project,
    extract_requirements,
)

from agents.freelancer_agent import (
    compute_price_floor,
)

from agents.mediator_agent import (
    run_negotiation,
)

from db import operations as db


CLIENT_PROFILE_ID = "72531437-5384-4aee-8734-38898c2f9547"

# Replace with a real freelancer profile UUID
FREELANCER_PROFILE_ID = "f56e5c10-e2ab-431c-9f36-02c2267c079e"

RATE_EXPECTATION = 45.0


BRIEF = """
Need a React portfolio website.

Pages:
- Home
- About
- Projects
- Contact

Responsive.

Delivery in 2 weeks.

Budget around $70/hr.
"""


def divider(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def main():

    ############################################################
    # CLIENT
    ############################################################

    divider("STEP 1 — CREATE PROJECT")

    project, version = create_project(
        client_profile_id=CLIENT_PROFILE_ID,
        title="Pipeline Smoke Test",
        brief_text=BRIEF,
    )

    project_id = str(project.project_id)
    version_id = str(version.version_id)

    print("Project :", project_id)
    print("Version :", version_id)

    ############################################################

    divider("STEP 2 — REQUIREMENT EXTRACTION")

    gaps = extract_requirements(
        project_id=project_id,
        version_id=version_id,
        brief_text=BRIEF,
    )

    requirements = db.get_requirements_by_version(version_id)

    print(f"{len(requirements)} requirement(s) extracted")
    print(f"{len(gaps)} gap(s) detected")

    ############################################################
    # FREELANCER
    ############################################################

    divider("STEP 3 — PRICE FLOOR")

    floor = compute_price_floor(
        project_id=project_id,
        version_id=version_id,
        freelancer_profile_id=FREELANCER_PROFILE_ID,
        rate_expectation=RATE_EXPECTATION,
    )

    print()

    print("Price Floor")

    print("----------------------------")

    print(f"Amount      : ${floor.amount}/hr")
    print(f"Confidence  : {floor.confidence}")
    print(f"Reasoning   : {floor.reasoning}")

    ############################################################
    # MEDIATOR
    ############################################################

    divider("STEP 4 — NEGOTIATION")

    negotiation = run_negotiation(
        project_id=project_id,
        version_id=version_id,
    )

    print()

    print("Negotiation")

    print("----------------------------")

    print("Status        :", negotiation.status)
    print("Floor         :", negotiation.floor)
    print("Ceiling       :", negotiation.ceiling)
    print("Current Offer :", negotiation.current_offer)
    print("Rounds        :", negotiation.round_count)

    ############################################################
    # VERIFY DATABASE
    ############################################################

    divider("STEP 5 — VERIFY DATABASE")

    floor_row = db.get_price_floor_by_version(version_id)

    assert floor_row is not None

    print("✓ Price floor saved")

    comparables = db.get_comparables_by_price_floor(
        str(floor.price_floor_id)
    )

    print(f"✓ {len(comparables)} comparables")

    state = db.get_negotiation_state(project_id)

    assert state is not None

    print("✓ Negotiation state saved")

    rounds = db.get_negotiation_rounds(
        state["negotiation_id"]
    )

    print(f"✓ {len(rounds)} negotiation rounds")

    ############################################################

    divider("NEGOTIATION HISTORY")

    for r in rounds:

        print(f"\nRound {r['round_number']}")
        print(f"Offer : ${r['offer']}/hr")
        print(f"Actor : {r['actor']}")
        print(r["message"])

    ############################################################

    divider("PIPELINE COMPLETE")

    print()

    print("✓ Client Agent")

    print("✓ Requirement Extraction")

    print("✓ Freelancer Agent")

    print("✓ Price Floor")

    print("✓ Negotiation")

    print("✓ Database")

    print()

    print("END-TO-END PIPELINE PASSED")


if __name__ == "__main__":
    main()