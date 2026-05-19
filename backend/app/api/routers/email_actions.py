"""Email-click GET endpoints for invitation Accept / Decline links.

Email clients can only render plain anchor tags (no JavaScript, no POST
forms in many clients). The Accept / Decline buttons in the invitation
email therefore link to these endpoints, which:

  * resolve the invitation by id (the id itself is the bearer token — the
    same pattern Calendly / Eventbrite use for one-click RSVPs),
  * flip ``invitations.status`` to ``accepted`` or ``declined`` idempotently,
  * return a small, calm HTML confirmation page.

We keep this router intentionally separate from ``/api/invitations`` so
the JSON API stays clean and machine-readable while these routes stay
browser-friendly.
"""

from __future__ import annotations

import os
from sqlite3 import Connection

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app.api.deps import get_connection
from app.repositories import ActivityRepository

router = APIRouter(prefix="/r/invitations", tags=["email-actions"])


_DEFAULT_APP_BASE_URL = "http://127.0.0.1:3001"


def _app_base_url() -> str:
    return (os.environ.get("APP_BASE_URL") or _DEFAULT_APP_BASE_URL).rstrip("/")


def _page(*, heading: str, body: str, view_url: str | None = None) -> str:
    """Render a calm, minimal HTML confirmation page (inline styles for portability)."""
    app_link_block = ""
    if view_url:
        app_link_block = (
            f'<p style="margin-top:24px;">'
            f'<a href="{view_url}" '
            f'style="color:#3e6b3e;text-decoration:underline;font-size:15px;">'
            f"View activity in the app"
            f"</a></p>"
        )
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>CivicCircles</title>
  </head>
  <body style="margin:0;padding:0;background:#f7f5f1;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;color:#2f3a2f;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr>
        <td align="center" style="padding:48px 16px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:480px;background:#ffffff;border-radius:18px;border:1px solid #e4e0d8;box-shadow:0 2px 8px rgba(60,55,40,0.04);">
            <tr>
              <td style="padding:32px 32px 8px 32px;font-size:13px;letter-spacing:0.08em;text-transform:uppercase;color:#7d8a7d;">
                CivicCircles
              </td>
            </tr>
            <tr>
              <td style="padding:8px 32px 8px 32px;font-size:22px;line-height:1.35;font-weight:500;color:#2f3a2f;">
                {heading}
              </td>
            </tr>
            <tr>
              <td style="padding:8px 32px 32px 32px;font-size:15px;line-height:1.6;color:#4a564a;">
                {body}
                {app_link_block}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


def _flip_invitation_status(
    conn: Connection,
    invitation_id: str,
    new_status: str,
    *,
    companion_pass_used: bool | None = None,
) -> tuple[bool, dict | None]:
    """Set ``invitations.status`` idempotently. Returns (found, row dict).

    When ``companion_pass_used`` is provided it is persisted alongside the
    status update — used by the "Bring someone I trust" CTA which flips
    the invitation to ``accepted`` and records the companion pass.
    """
    row = conn.execute(
        "SELECT * FROM invitations WHERE id = ?", (invitation_id,)
    ).fetchone()
    if row is None:
        return False, None
    needs_status_change = row["status"] != new_status
    needs_companion_change = (
        companion_pass_used is not None
        and bool(row["companion_pass_used"]) != companion_pass_used
    )
    if needs_status_change or needs_companion_change:
        ActivityRepository(conn).update_invitation_status(
            invitation_id=invitation_id,
            status=new_status,
            companion_pass_used=companion_pass_used,
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM invitations WHERE id = ?", (invitation_id,)
        ).fetchone()
    return True, dict(row)


def _activity_view_url(activity_id: str | None) -> str | None:
    if not activity_id:
        return None
    return f"{_app_base_url()}/inbox?activity_id={activity_id}"


@router.get(
    "/{invitation_id}/accept",
    response_class=HTMLResponse,
    summary="Email-click endpoint: mark invitation as accepted",
)
def accept_via_email(
    invitation_id: str,
    conn: Connection = Depends(get_connection),
) -> HTMLResponse:
    found, row = _flip_invitation_status(conn, invitation_id, "accepted")
    if not found:
        html = _page(
            heading="That link looks expired",
            body=(
                "We couldn’t find that invitation. It may have been withdrawn "
                "or replaced with a fresher one — open the app to see what’s "
                "available now."
            ),
            view_url=_app_base_url(),
        )
        return HTMLResponse(html, status_code=404)
    html = _page(
        heading="You’re in.",
        body=(
            "Thanks for saying yes. The host will see you on the list. "
            "You can still change your mind any time before the activity."
        ),
        view_url=_activity_view_url(row.get("activity_id")) if row else None,
    )
    return HTMLResponse(html)


@router.get(
    "/{invitation_id}/accept-with-companion",
    response_class=HTMLResponse,
    summary="Email-click endpoint: accept and bring a trusted companion",
)
def accept_with_companion_via_email(
    invitation_id: str,
    conn: Connection = Depends(get_connection),
) -> HTMLResponse:
    found, row = _flip_invitation_status(
        conn, invitation_id, "accepted", companion_pass_used=True
    )
    if not found:
        html = _page(
            heading="That link looks expired",
            body=(
                "We couldn’t find that invitation. Open the app to see what’s "
                "available now."
            ),
            view_url=_app_base_url(),
        )
        return HTMLResponse(html, status_code=404)
    html = _page(
        heading="You’re in, plus one.",
        body=(
            "We’ve noted you’re bringing someone you trust. The host will "
            "see two seats reserved for your circle."
        ),
        view_url=_activity_view_url(row.get("activity_id")) if row else None,
    )
    return HTMLResponse(html)


@router.get(
    "/{invitation_id}/decline",
    response_class=HTMLResponse,
    summary="Email-click endpoint: mark invitation as declined",
)
def decline_via_email(
    invitation_id: str,
    conn: Connection = Depends(get_connection),
) -> HTMLResponse:
    found, row = _flip_invitation_status(conn, invitation_id, "declined")
    if not found:
        html = _page(
            heading="That link looks expired",
            body=(
                "We couldn’t find that invitation. No action needed — feel "
                "free to close this tab."
            ),
            view_url=_app_base_url(),
        )
        return HTMLResponse(html, status_code=404)
    html = _page(
        heading="That’s okay.",
        body=(
            "Not this time is always okay. We’ll keep an eye out for "
            "something that fits better and let you know."
        ),
        view_url=_activity_view_url(row.get("activity_id")) if row else None,
    )
    return HTMLResponse(html)
