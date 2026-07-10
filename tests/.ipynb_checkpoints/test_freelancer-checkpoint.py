"""
tests/test_freelancer_agent.py

Smoke test for the Freelancer Agent.

Flow:
1. Create a project
2. Create first project version
3. Compute a price floor
4. Verify it was saved
5. Verify comparables were saved
"""

from agents.freelancer_agent import compute_price_floor
from db import operations as db

CLIENT_PROFILE_ID = "72531437-5384-4aee-8734-38898c2f9547"

# Use an existing freelancer profile in your database.
# Replace this UUID if necessary.
FREELANCER_PROFILE_ID = '55923ca9-4fc7-4bc0-a38a-3e548a07d29e'

RATE_EXPECTATION = 45.0


def divider(title: str):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main():

    divider("STEP 1 — CREATE PROJECT")

    result = db.save_project(
        {
            "client_profile_id": CLIENT_PROFILE_ID,
            "title": "Freelancer Agent Smoke Test",
            "description": "Build a React landing page.",
            "status": "draft",
        }
    )

    project = result["project"]
    version = result["version"]

    project_id = str(project["project_id"])
    version_id = str(version["version_id"])

    print("Project ID :", project_id)
    print("Version ID :", version_id)

    divider("STEP 2 — COMPUTE PRICE FLOOR")

    floor = compute_price_floor(
        project_id=project_id,
        version_id=version_id,
        freelancer_profile_id=FREELANCER_PROFILE_ID,
        rate_expectation=RATE_EXPECTATION,
    )

    print("Price Floor")
    print("---------------------------")
    print(f"Amount      : ${floor.amount}/hr")
    print(f"Confidence  : {floor.confidence}")
    print(f"Reasoning   : {floor.reasoning}")

    divider("STEP 3 — VERIFY DATABASE")

    floor_row = db.get_price_floor_by_version(version_id)

    assert floor_row is not None, "Price floor was not saved."

    print("✓ Price floor exists.")

    comparables = db.get_comparables_by_price_floor(
        str(floor.price_floor_id)
    )

    print(f"Comparable count: {len(comparables)}")

    assert len(comparables) > 0, "No comparables saved."

    print("✓ Comparables saved.")

    divider("COMPARABLES")

    for i, comp in enumerate(comparables, start=1):
        print(f"{i}. {comp['text']}")

    divider("DONE")

    print("✓ Freelancer Agent smoke test PASSED")


if __name__ == "__main__":
    main()