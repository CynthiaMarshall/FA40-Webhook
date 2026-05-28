"""
Freedom After 40 - Blueprint PDF Webhook Receiver
Receives JSON from Lovable, generates a PDF, emails it via Resend
or returns it as a direct download.
"""

import os
import base64
import logging
from flask import Flask, request, jsonify, send_file, make_response
import io
import resend

from fa40_blueprint_pdf import generate_pdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)

RESEND_API_KEY  = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL      = os.environ.get("FROM_EMAIL", "Freedom After 40 <hello@freedomafter40.com>")
WEBHOOK_SECRET  = os.environ.get("WEBHOOK_SECRET", "")  # optional gate

resend.api_key = RESEND_API_KEY


# ── blueprintType → type mapping ──────────────────────────────────────────────
BLUEPRINT_TYPE_MAP = {
    "free":     "blueprint",
    "enhanced": "enhanced",
    "income":   "income",
}

EMAIL_SUBJECTS = {
    "blueprint": "Your Freedom Blueprint is Ready",
    "enhanced":  "Your Enhanced Blueprint is Ready",
    "income":    "Your Income Freedom Builder is Ready",
}


def _email_html(pdf_type: str, first_name: str) -> str:
    name_line = f"Hi {first_name}," if first_name else "Hi,"
    if pdf_type == "enhanced":
        headline = "Your Enhanced Blueprint is attached."
        body = (
            "You went deeper, and what we found is worth reading carefully. "
            "Your Enhanced Blueprint is built entirely around your assessments, "
            "your strengths, and the patterns we noticed in your answers."
        )
    elif pdf_type == "income":
        headline = "Your Income Freedom Builder is attached."
        body = (
            "Inside you'll find your viability score, your ideal buyer profile, "
            "pricing range, and three income concepts built from your story."
        )
    else:
        headline = "Your Freedom Blueprint is attached."
        body = (
            "It's built from your answers and reflects where you are right now: "
            "what's already working, where you need support, and your income concepts."
        )

    return f"""
<html>
<body style="margin:0;padding:0;background:#FAF7F2;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#FAF7F2;">
    <tr><td align="center" style="padding:40px 16px;">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:8px;overflow:hidden;
                    border:1px solid #E0D5D8;max-width:600px;">

        <!-- Header band -->
        <tr>
          <td style="background:#3D1F3D;padding:32px 40px 28px;">
            <p style="margin:0;font-size:11px;letter-spacing:3px;color:#C9A84C;
                      font-weight:600;text-transform:uppercase;">Freedom After 40</p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:36px 40px 28px;">
            <p style="margin:0 0 8px;font-size:15px;color:#4A3840;">{name_line}</p>
            <p style="margin:0 0 20px;font-size:22px;font-weight:600;color:#3D1F3D;
                      line-height:1.3;">{headline}</p>
            <p style="margin:0 0 24px;font-size:15px;color:#4A3840;line-height:1.6;">
              {body}
            </p>
            <p style="margin:0 0 8px;font-size:15px;color:#4A3840;line-height:1.6;">
              Open the PDF attached to this email and read it somewhere quiet.
            </p>
          </td>
        </tr>

        <!-- Gold rule + signature -->
        <tr>
          <td style="padding:0 40px 36px;">
            <div style="height:1px;background:#C9A84C;margin-bottom:24px;"></div>
            <p style="margin:0;font-size:14px;color:#4A3840;">To your freedom,</p>
            <p style="margin:4px 0 0;font-size:20px;color:#3D1F3D;font-style:italic;">Cynthia</p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#F0EBE3;padding:16px 40px;text-align:center;
                     border-top:1px solid #E0D5D8;">
            <p style="margin:0;font-size:11px;color:#8B7580;">
              Freedom After 40 &bull; freedomafter40.com &bull; hello@freedomafter40.com
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
"""


def _pdf_filename(pdf_type: str, first_name: str, last_name: str) -> str:
    parts = ["FA40"]
    if pdf_type == "enhanced":
        parts.append("Enhanced_Blueprint")
    elif pdf_type == "income":
        parts.append("Income_Builder")
    else:
        parts.append("Freedom_Blueprint")
    name = f"{first_name}_{last_name}".strip("_")
    if name:
        parts.append(name)
    return "_".join(parts) + ".pdf"


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/download-pdf")
def download_pdf():
    """Generate a PDF and return it as a direct file download."""
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "invalid JSON"}), 400

    session_id     = payload.get("sessionId", "unknown")
    blueprint_type = payload.get("blueprintType", "free")
    email          = payload.get("email", "").strip()
    first_name     = payload.get("stripe_first_name", "").strip()
    last_name      = payload.get("stripe_last_name", "").strip()

    log.info("Download PDF request: session=%s type=%s email=%s", session_id, blueprint_type, email)

    pdf_type = BLUEPRINT_TYPE_MAP.get(blueprint_type, "blueprint")

    data = {
        **payload,
        "type":      pdf_type,
        "sessionId": session_id,
    }

    pdf_path = None
    try:
        pdf_path = generate_pdf(data)
        log.info("PDF generated for download: %s", pdf_path)
    except Exception as exc:
        log.exception("PDF generation failed: %s", exc)
        return jsonify({"error": "pdf_generation_failed", "detail": str(exc)}), 500

    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
    except Exception as exc:
        log.exception("Could not read PDF: %s", exc)
        return jsonify({"error": "pdf_read_failed"}), 500
    finally:
        if pdf_path and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except OSError:
                pass

    filename = _pdf_filename(pdf_type, first_name, last_name)

    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


@app.options("/download-pdf")
def download_pdf_preflight():
    """Handle CORS preflight for the download endpoint."""
    response = make_response()
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.post("/webhook")
def webhook():
    # Optional secret gate
    if WEBHOOK_SECRET:
        incoming = request.headers.get("X-Webhook-Secret", "")
        if incoming != WEBHOOK_SECRET:
            log.warning("Rejected webhook: bad secret")
            return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "invalid JSON"}), 400

    session_id     = payload.get("sessionId", "unknown")
    blueprint_type = payload.get("blueprintType", "free")
    email          = payload.get("email", "").strip()
    first_name     = payload.get("stripe_first_name", "").strip()
    last_name      = payload.get("stripe_last_name", "").strip()

    log.info("Webhook received: session=%s type=%s email=%s", session_id, blueprint_type, email)

    if not email:
        return jsonify({"error": "email is required"}), 422

    pdf_type = BLUEPRINT_TYPE_MAP.get(blueprint_type, "blueprint")

    # Build the data dict the PDF generator expects
    data = {
        **payload,
        "type":      pdf_type,
        "sessionId": session_id,
    }

    # Generate PDF
    pdf_path = None
    try:
        pdf_path = generate_pdf(data)
        log.info("PDF generated: %s", pdf_path)
    except Exception as exc:
        log.exception("PDF generation failed: %s", exc)
        return jsonify({"error": "pdf_generation_failed", "detail": str(exc)}), 500

    # Read and encode PDF
    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
    except Exception as exc:
        log.exception("Could not read PDF: %s", exc)
        return jsonify({"error": "pdf_read_failed"}), 500
    finally:
        if pdf_path and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except OSError:
                pass

    # Send via Resend
    if not RESEND_API_KEY:
        log.warning("RESEND_API_KEY not set — skipping email send")
        return jsonify({"status": "pdf_generated_no_email", "session": session_id})

    filename = _pdf_filename(pdf_type, first_name, last_name)
    subject  = EMAIL_SUBJECTS.get(pdf_type, "Your Blueprint is Ready")
    html     = _email_html(pdf_type, first_name)

    try:
        resp = resend.Emails.send({
            "from":    FROM_EMAIL,
            "to":      [email],
            "subject": subject,
            "html":    html,
            "attachments": [{
                "filename": filename,
                "content":  list(pdf_bytes),
            }],
        })
        log.info("Email sent: id=%s to=%s", resp.get("id"), email)
    except Exception as exc:
        log.exception("Resend failed: %s", exc)
        return jsonify({"error": "email_failed", "detail": str(exc)}), 500

    return jsonify({
        "status":  "ok",
        "session": session_id,
        "email":   email,
        "type":    pdf_type,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
