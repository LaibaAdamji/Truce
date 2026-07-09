"""
tools/contract_generator.py
Generates a signed-style scope-and-milestone contract PDF once a negotiation
has converged. Called from crew.py immediately after mediator_agent.run_negotiation()
returns a NegotiationState with status == "converged".

No LLM calls here on purpose — this is the one deliverable in the pipeline
that should be fully deterministic. The scope/price/parties are already
decided by the time this runs; this module just formats what exists.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib import colors

from db import operations as db
from db.client import supabase
from models.schemas import NegotiationState

OUTPUT_DIR = Path("generated_contracts")
BUCKET_NAME = "contracts"


class ContractGeneratorError(Exception):
    pass


class ContractUploadError(Exception):
    pass


def upload_contract_to_bucket(local_path: Path, project_id: str, expires_in: int = 60 * 60 * 24 * 7) -> str:
    """
    Upload a local PDF to the private Supabase 'contracts' bucket and return
    a time-limited signed URL (bucket is private, so get_public_url() would
    return an inaccessible link). Default expiry: 7 days -- adjust based on
    how long clients/freelancers need access to review/download.
    """
    storage_path = f"{project_id}/contract.pdf"

    with open(local_path, "rb") as f:
        file_bytes = f.read()

    try:
        supabase.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
    except Exception as exc:  # supabase-py raises its own StorageException type;
        # broad catch here on purpose since the exact exception class varies
        # by supabase-py version - tighten this once you confirm which one.
        raise ContractUploadError(f"Failed to upload contract PDF: {exc}") from exc

    try:
        signed = supabase.storage.from_(BUCKET_NAME).create_signed_url(
            storage_path, expires_in
        )
    except Exception as exc:
        raise ContractUploadError(f"Failed to generate signed URL: {exc}") from exc

    # supabase-py returns {"signedURL": "..."} (older) or {"signedUrl": "..."}
    # depending on version -- handle both keys defensively.
    signed_url = signed.get("signedURL") or signed.get("signedUrl")
    if not signed_url:
        raise ContractUploadError(f"Unexpected signed URL response shape: {signed}")

    return signed_url


def generate_contract(project_id: str, version_id: str) -> str:
    """
    Build a PDF contract from converged negotiation state + finalized scope.
    Returns a signed URL to the uploaded PDF. Raises ContractGeneratorError
    if negotiation isn't actually converged or required data is missing.
    """
    negotiation = _load_negotiation(project_id)
    if negotiation.status != "converged":
        raise ContractGeneratorError(
            f"Cannot generate contract: negotiation status is "
            f"'{negotiation.status}', not 'converged'"
        )

    project = _load_project(project_id)
    requirements = _load_scope_requirements(version_id)
    client_name, freelancer_name = _load_party_names(project)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    file_path = OUTPUT_DIR / f"contract_{project_id}.pdf"

    _render_pdf(
        path=file_path,
        project_title=project.get("title", "Untitled Project"),
        client_name=client_name,
        freelancer_name=freelancer_name,
        rate=negotiation.current_offer,
        requirements=requirements,
        generated_at=datetime.now(timezone.utc),
    )

    contract_url = upload_contract_to_bucket(file_path, project_id)
    storage_path = f"{project_id}/contract.pdf"

    existing = db.get_contract_by_project(project_id)
    next_version = (existing["version"] + 1) if existing else 1
    contract_row = db.save_contract({
        "project_id": project_id,
        "version": next_version,
        "storage_path": storage_path,
        "file_type": "pdf",
        "status": "draft",
        "generated_by": "contract_generator_agent",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    })
    if contract_row is None:
        raise ContractGeneratorError("PDF uploaded but failed to save contracts row")

    db.update_project_status(project_id, "contract_generated")

    # Local file is kept as-is (not deleted) in case you want it for
    # debugging/demo fallback if the bucket upload path has issues.
    # NOTE: contract_url is a signed URL with a 7-day expiry (see
    # upload_contract_to_bucket). Don't persist it directly anywhere long-
    # lived -- regenerate from storage_path when a fresh link is needed:
    #   supabase.storage.from_(BUCKET_NAME).create_signed_url(storage_path, expires_in)
    return contract_url


# ---------------------------------------------------------------------------
# Data loading — thin wrappers so the render function stays pure/testable.
# Adjust the db.operations calls below to match your actual function names;
# these mirror the pattern already used in mediator_agent.py.
# ---------------------------------------------------------------------------

def _load_negotiation(project_id: str) -> NegotiationState:
    row = db.get_negotiation_state(project_id)
    if row is None:
        raise ContractGeneratorError(f"No negotiation state found for project {project_id}")
    return NegotiationState(**row)


def _load_project(project_id: str) -> dict:
    project = db.get_project(project_id)
    if project is None:
        raise ContractGeneratorError(f"No project found for {project_id}")
    return project


def _load_scope_requirements(version_id: str) -> list[dict]:
    reqs = db.get_requirements_by_version(version_id)
    # Keep only the finalized scope items, not the budget requirement itself.
    return [r for r in reqs if r.get("type") != "budget"]


def _load_party_names(project: dict) -> tuple[str, str]:
    """
    ClientProfile/FreelancerProfile carry no name field -- names live on
    Profiles, joined via user_id. Falls back to a generic label only if
    a profile or its parent Profiles row is genuinely missing.
    """
    client_name = "Client"
    freelancer_name = "Freelancer"

    client_profile_id = project.get("client_profile_id")
    if client_profile_id:
        client_profile = db.get_client_profile(client_profile_id)
        if client_profile and client_profile.get("user_id"):
            user = db.get_profile(client_profile["user_id"])
            if user and user.get("name"):
                client_name = user["name"]

    freelancer_profile_id = project.get("freelancer_profile_id")
    if freelancer_profile_id:
        freelancer_profile = db.get_freelancer_profile(freelancer_profile_id)
        if freelancer_profile and freelancer_profile.get("user_id"):
            user = db.get_profile(freelancer_profile["user_id"])
            if user and user.get("name"):
                freelancer_name = user["name"]

    return client_name, freelancer_name


# ---------------------------------------------------------------------------
# Pure rendering — no DB calls below this line, easy to unit test standalone.
# ---------------------------------------------------------------------------

def _render_pdf(
    path: Path,
    project_title: str,
    client_name: str,
    freelancer_name: str,
    rate: float,
    requirements: list[dict],
    generated_at: datetime,
) -> None:
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ContractTitle", parent=styles["Title"], fontSize=20, spaceAfter=4
    )
    h2_style = ParagraphStyle(
        "SectionHeader", parent=styles["Heading2"], spaceBefore=16, spaceAfter=6
    )
    body_style = styles["BodyText"]
    small_style = ParagraphStyle(
        "Small", parent=styles["BodyText"], fontSize=9, textColor=colors.grey
    )

    doc = SimpleDocTemplate(
        str(path), pagesize=LETTER,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )

    story = []

    story.append(Paragraph("Scope &amp; Rate Agreement", title_style))
    story.append(Paragraph(project_title, styles["Heading3"]))
    story.append(
        Paragraph(
            f"Generated {generated_at.strftime('%B %d, %Y at %H:%M UTC')} "
            "via Truce negotiation pipeline",
            small_style,
        )
    )
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceBefore=10, spaceAfter=10))

    # Parties
    story.append(Paragraph("Parties", h2_style))
    party_table = Table(
        [["Client", client_name], ["Freelancer", freelancer_name]],
        colWidths=[1.5 * inch, 4 * inch],
    )
    party_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(party_table)

    # Agreed rate
    story.append(Paragraph("Agreed Rate", h2_style))
    story.append(Paragraph(
        f"<b>${rate:.2f}/hr</b> — reached via automated negotiation between "
        f"client budget ceiling and freelancer price floor.",
        body_style,
    ))

    # Scope
    story.append(Paragraph("Scope of Work", h2_style))
    if requirements:
        for req in requirements:
            label = req.get("value", str(req))
            story.append(Paragraph(f"• {label}", body_style))
    else:
        story.append(Paragraph("No itemized scope requirements on file.", body_style))

    # Signature block
    story.append(Spacer(1, 0.6 * inch))
    story.append(Paragraph("Signatures", h2_style))
    sig_table = Table(
        [
            ["_______________________________", "_______________________________"],
            [client_name, freelancer_name],
            ["Date: ___________", "Date: ___________"],
        ],
        colWidths=[2.75 * inch, 2.75 * inch],
    )
    sig_table.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, 0), 24),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
    ]))
    story.append(sig_table)

    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(
        "This document was generated automatically based on an AI-mediated "
        "rate negotiation and is intended as a draft scope agreement, not a "
        "substitute for legal review.",
        small_style,
    ))

    doc.build(story)