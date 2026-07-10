"""
ui/pages/contract.py
Shows the scope that will go into the contract + agreed rate, triggers
contract generation once negotiation has converged, and surfaces the
generated contract for viewing and download. Reads project_id from
st.session_state["active_project_id"] (same convention as negotiation.py).

Calls into tools.contract_generator directly -- no backend logic here,
this page only orchestrates + visualizes, same as negotiation.py.

--------------------------------------------------------------------------
Verified against the real tools/contract_generator.py and db/operations.py:

  contract_generator.generate_contract(project_id, version_id) -> str
      Two args only (no negotiation_id -- it loads negotiation state
      internally). Returns a signed URL string directly, NOT a dict.
      Raises ContractGeneratorError if negotiation isn't converged or
      required data is missing; ContractUploadError if the Storage
      upload/signing step fails.

  db.get_contract_by_project(project_id) -> dict | None
      Real fields: project_id, version (int), storage_path, file_type,
      status ("draft"/etc), generated_by, generated_at. No contract_id
      in the insert payload, so this page keys off `version` instead.

  Scope preview uses the SAME source data as the PDF itself:
  db.get_requirements_by_version(version_id), filtered to exclude
  type == "budget", per contract_generator._load_scope_requirements().
  (scope_items/scope_documents exist in the schema but the generator
  doesn't read them, so showing scope_items here could drift from what
  actually ends up in the PDF -- deliberately avoided.)

  db.get_contract_download_url(storage_path) now exists in db/operations.py
  (re-signs an already-uploaded contract PDF without re-uploading) -- the
  AttributeError fallback below is just a safety net in case an older
  db/operations.py is deployed somewhere.
--------------------------------------------------------------------------
"""
import streamlit as st

from db import operations as db
from tools import contract_generator
from tools.contract_generator import ContractGeneratorError, ContractUploadError
from ui.theme import status_badge_html


def _back_to_dashboard() -> None:
    st.session_state["page"] = "dashboard"
    st.session_state.pop("active_project_id", None)


def _back_to_negotiation() -> None:
    st.session_state["page"] = "negotiation"


def render() -> None:
    project_id = st.session_state.get("active_project_id")
    if not project_id:
        st.warning("No project selected.")
        if st.button("← Back to Dashboard"):
            _back_to_dashboard()
            st.rerun()
        return

    project = db.get_project(project_id)
    if not project:
        st.error("Project not found.")
        return

    version = db.get_latest_version(project_id)
    version_id = version["version_id"] if version else None

    negotiation = db.get_negotiation_state(project_id)

    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button("←", help="Back to dashboard"):
            _back_to_dashboard()
            st.rerun()
    with col_title:
        st.title(project.get("title", "Project"))
        st.markdown(status_badge_html(project.get("status", "draft")), unsafe_allow_html=True)

    st.markdown("---")

    if not negotiation or negotiation.get("status") != "converged":
        _render_not_ready(negotiation)
        return

    contract = db.get_contract_by_project(project_id)

    _render_agreement_summary(negotiation)
    st.markdown("---")

    if not contract:
        _render_generate_section(project_id, version_id, negotiation)
    else:
        _render_scope_section(version_id)
        st.markdown("---")
        _render_contract_viewer(contract, project_id, version_id)


def _render_not_ready(negotiation: dict | None) -> None:
    st.markdown("### Contract")
    if not negotiation:
        icon, msg = "🤝", "Negotiation hasn't started yet. Head to the Negotiation tab first."
    elif negotiation.get("status") == "capped_no_deal":
        icon, msg = "⚠️", "This negotiation ended without a deal, so there's nothing to contract yet."
    else:
        icon, msg = "📝", "Contract generation unlocks once the negotiation converges on a final rate."
    st.markdown(
        f"""
        <div class="truce-empty-state">
            <div class="truce-empty-icon">{icon}</div>
            <p style="margin:0;">{msg}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("← Back to Negotiation"):
        _back_to_negotiation()
        st.rerun()


def _render_agreement_summary(negotiation: dict) -> None:
    st.markdown(
        f"""
        <div class="truce-card-glass" style="text-align:center;">
            <p class="truce-secondary" style="margin:0;">Agreed rate</p>
            <p style="font-size:2.4rem; font-weight:600; margin:4px 0;">
                ${negotiation['current_offer']:.2f}/hr
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_generate_section(project_id: str, version_id: str | None, negotiation: dict) -> None:
    st.markdown("### Generate Contract")
    st.markdown(
        '<p class="truce-secondary">Negotiation has converged. Generate the contract '
        "artifact to review scope, terms, and the agreed rate before download.</p>",
        unsafe_allow_html=True,
    )
    if not version_id:
        st.info("No project version found yet.")
        return

    if st.button("Generate Contract", type="primary"):
        with st.spinner("Drafting the contract..."):
            try:
                contract_generator.generate_contract(project_id, version_id)
            except ContractGeneratorError as e:
                st.error(f"Contract generation failed: {e}")
                return
            except ContractUploadError as e:
                st.error(f"Contract was drafted but couldn't be uploaded: {e}")
                return
            except Exception as e:
                st.error(f"Unexpected error generating the contract: {e}")
                return
        st.rerun()


def _render_scope_section(version_id: str | None) -> None:
    """
    Mirrors contract_generator._load_scope_requirements() exactly (same
    filter, same source table) so this preview never drifts from what the
    generated PDF's "Scope of Work" section actually contains.
    """
    st.markdown("### Scope")

    if not version_id:
        st.info("No project version found yet.")
        return

    requirements = db.get_requirements_by_version(version_id)
    scope_items = [r for r in requirements if r.get("type") != "budget"]

    if not scope_items:
        st.markdown(
            """
            <div class="truce-empty-state">
                <div class="truce-empty-icon">📋</div>
                <p style="margin:0;">No itemized scope requirements on file.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for req in scope_items:
        st.markdown(
            f"""
            <div class="truce-card" style="margin-bottom:10px;">
                <p style="margin:0;">{req.get('value', str(req))}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_contract_viewer(contract: dict, project_id: str, version_id: str | None) -> None:
    st.markdown("### Contract")

    status = contract.get("status", "draft")
    status_labels = {
        "draft": ("Draft", "truce-badge-pending"),
        "signed": ("Signed", "truce-badge-success"),
    }
    label, badge_class = status_labels.get(status, (status.title(), "truce-badge-pending"))

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(
            f'<span class="truce-badge {badge_class}">{label}</span> '
            f'<span class="truce-secondary" style="font-size:0.85rem;">'
            f'v{contract.get("version", 1)}</span>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'<p class="truce-secondary" style="margin:0; text-align:right;">'
            f'{contract.get("file_type", "pdf").upper()}</p>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    _render_download_section(contract)

    if status == "draft":
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("Scope changed? Regenerate the contract"):
            st.markdown(
                '<p class="truce-secondary" style="margin:0 0 8px 0;">'
                "Creates a new version from the current scope and rate. "
                "The previous version stays on file.</p>",
                unsafe_allow_html=True,
            )
            if st.button("Regenerate Contract"):
                with st.spinner("Redrafting the contract..."):
                    try:
                        contract_generator.generate_contract(project_id, version_id)
                    except (ContractGeneratorError, ContractUploadError) as e:
                        st.error(f"Regeneration failed: {e}")
                        return
                st.rerun()


def _render_download_section(contract: dict) -> None:
    storage_path = contract.get("storage_path")
    if not storage_path:
        st.warning("Contract record exists but has no storage path yet.")
        return

    try:
        # Requires db.get_contract_download_url() -- see the module
        # docstring at the top of this file for the function to add to
        # db/operations.py; it doesn't exist there yet.
        download_url = db.get_contract_download_url(storage_path)
        st.link_button("Download Contract →", download_url, type="primary")
    except AttributeError:
        st.error(
            "db.get_contract_download_url() isn't defined yet -- see the "
            "docstring at the top of this file for the snippet to add to "
            "db/operations.py."
        )
    except Exception as e:
        st.error(f"Couldn't prepare the download: {e}")