"""
tests/test_client_agent.py

End-to-end smoke test for the Client Agent.

Flow:
1. Create project
2. Extract requirements
3. Print requirements
4. Print gaps
5. Print clarification questions
6. (Optional) Submit answers
7. Finalize scope
"""

from agents.client_agent import (
    create_project,
    extract_requirements,
    submit_clarifications,
    finalize_scope,
    get_clarifications_for_version,
)

from db import operations as db


CLIENT_PROFILE_ID = "72531437-5384-4aee-8734-38898c2f9547"


BRIEF = """
Need a React portfolio website.

Pages:
- Home
- About
- Projects
- Contact

Should be mobile responsive.

Need it finished in about 2 weeks.

Budget is around $700.
"""


def divider(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main():

    divider("STEP 1 — CREATE PROJECT")

    project, version = create_project(
        client_profile_id=CLIENT_PROFILE_ID,
        title="Client Agent Smoke Test",
        brief_text=BRIEF,
    )

    print("Project ID :", project.project_id)
    print("Version ID :", version.version_id)

    divider("STEP 2 — REQUIREMENT EXTRACTION")

    gaps = extract_requirements(
        project_id=str(project.project_id),
        version_id=str(version.version_id),
        brief_text=BRIEF,
    )

    requirements = db.get_requirements_by_version(str(version.version_id))

    print(f"{len(requirements)} requirements extracted.\n")

    for req in requirements:
        print(req)

    divider("STEP 3 — GAPS")

    print(f"{len(gaps)} gap(s) detected.\n")

    for gap in gaps:
        print(gap)

    divider("STEP 4 — CLARIFICATION QUESTIONS")

    clarifications = get_clarifications_for_version(
        str(version.version_id)
    )

    print(f"{len(clarifications)} clarification(s).\n")

    for clar in clarifications:
        print(
            f"""
Question:
{clar.question_text}

Status:
{clar.status}
"""
        )

    if clarifications:

        divider("STEP 5 — SUBMIT SAMPLE ANSWERS")

        answers = {}

        for clar in clarifications:
            answers[str(clar.gap_id)] = "2 weeks"

        new_gaps = submit_clarifications(
            project_id=str(project.project_id),
            version_id=str(version.version_id),
            answers=answers,
        )

        print(f"Remaining gaps: {len(new_gaps)}")

    divider("STEP 6 — FINALIZE SCOPE")

    scope = finalize_scope(
        project_id=str(project.project_id),
        version_id=str(version.version_id),
    )

    print(scope)

    divider("DONE")

    print("Client Agent smoke test completed successfully.")


if __name__ == "__main__":
    main()