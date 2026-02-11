from django.conf import settings
from django.core.mail import EmailMultiAlternatives
import html


def send_verification_code(email: str, code: str):
    """
    Sends a light-themed verification email with graphite background.
    """

    code_str = html.escape(str(code))
    site_name = getattr(settings, "SITE_NAME", "Cryphos")
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "hello@cryphos.com")

    subject = "Your Cryphos verification code"
    preheader = "Use this code to finish signing up. It expires in 10 minutes."

    BG_URL = "https://cryphos.com/bg.png"

    text = (
        f"{site_name} verification code: {code_str}\n\n"
        "This code expires in 10 minutes. If you didn’t request it, ignore this email."
    )

    html_message = f"""\
<!doctype html>
<html>
  <head>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
  </head>
  <body style="margin:0;padding:0;background:#f5f5f7;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;visibility:hidden;">
      {html.escape(preheader)}
    </div>

    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
           background="{BG_URL}"
           style="width:100%; background:#f5f5f7 url('{BG_URL}') center/cover no-repeat;">
      <tr>
        <td align="center" style="padding:24px 12px;">
          <!-- Card -->
          <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
                 style="width:600px; max-width:600px; background:#ffffff; border:1px solid #e0e0e0; border-radius:12px;">
            <tr>
              <td align="center" style="padding:26px 22px 10px 22px;">
                <img src="https://cryphos.com/logo_lila.png" width="60" height="60" alt="{html.escape(site_name)}" />
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:4px 22px 0 22px; font-family:Inter,Arial,Helvetica,sans-serif;">
                <h1 style="margin:10px 0; font-size:22px; line-height:1.3; font-weight:700; color:#111111;">
                  Verify your email
                </h1>
                <p style="margin:8px 0; font-size:14px; line-height:1.6; color:#444444;">
                  Enter this code to continue:
                </p>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:18px 22px 8px 22px;">
                <div style="
                  display:inline-block;
                  font-family:Inter,Arial,Helvetica,sans-serif;
                  font-size:26px;
                  font-weight:800;
                  letter-spacing:6px;
                  padding:14px 18px;
                  color:#ffffff;
                  background:#6a2e8e;
                  border-radius:12px;">
                  {code_str}
                </div>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:6px 22px 24px 22px; font-family:Inter,Arial,Helvetica,sans-serif;">
                <p style="margin:10px 0; font-size:12px; color:#666666;">
                  The code expires in 10 minutes. If you didn’t request it, you can ignore this email.
                </p>
              </td>
            </tr>
          </table>

          <!-- Footer -->
          <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
                 style="width:600px; max-width:600px;">
            <tr>
              <td align="center" style="padding:14px 0 0 0; font-family:Inter,Arial,Helvetica,sans-serif; font-size:11px; color:#888888;">
                © {html.escape(site_name)}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=from_email,
        to=[email],
    )
    msg.attach_alternative(html_message, "text/html")
    msg.send(fail_silently=False)


def send_reset_code(email: str, code: str):
    """
    Sends a light-themed password reset email with graphite background.
    """

    code_str = html.escape(str(code))
    site_name = getattr(settings, "SITE_NAME", "Cryphos")
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "hello@cryphos.com")

    subject = "Your Cryphos password reset code"
    preheader = "Use this code to reset your password. It expires in 10 minutes."

    BG_URL = "https://cryphos.com/bg.png"

    # Plain text fallback
    text = (
        f"{site_name} password reset code: {code_str}\n\n"
        "This code expires in 10 minutes. If you didn’t request it, ignore this email."
    )

    # HTML template
    html_message = f"""\
<!doctype html>
<html>
  <head>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
  </head>
  <body style="margin:0;padding:0;background:#f5f5f7;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;visibility:hidden;">
      {html.escape(preheader)}
    </div>

    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
           background="{BG_URL}"
           style="width:100%; background:#f5f5f7 url('{BG_URL}') center/cover no-repeat;">
      <tr>
        <td align="center" style="padding:24px 12px;">
          <!-- Card -->
          <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
                 style="width:600px; max-width:600px; background:#ffffff; border:1px solid #e0e0e0; border-radius:12px;">
            <tr>
              <td align="center" style="padding:26px 22px 10px 22px;">
                <img src="https://cryphos.com/logo_lila.png" width="60" height="60" alt="{html.escape(site_name)}" />
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:4px 22px 0 22px; font-family:Inter,Arial,Helvetica,sans-serif;">
                <h1 style="margin:10px 0; font-size:22px; line-height:1.3; font-weight:700; color:#111111;">
                  Reset your password
                </h1>
                <p style="margin:8px 0; font-size:14px; line-height:1.6; color:#444444;">
                  Enter this code to continue:
                </p>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:18px 22px 8px 22px;">
                <div style="
                  display:inline-block;
                  font-family:Inter,Arial,Helvetica,sans-serif;
                  font-size:26px;
                  font-weight:800;
                  letter-spacing:6px;
                  padding:14px 18px;
                  color:#ffffff;
                  background:#6a2e8e;
                  border-radius:12px;">
                  {code_str}
                </div>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:6px 22px 24px 22px; font-family:Inter,Arial,Helvetica,sans-serif;">
                <p style="margin:10px 0; font-size:12px; color:#666666;">
                  The code expires in 10 minutes. If you didn’t request it, you can ignore this email.
                </p>
              </td>
            </tr>
          </table>

          <!-- Footer -->
          <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
                 style="width:600px; max-width:600px;">
            <tr>
              <td align="center" style="padding:14px 0 0 0; font-family:Inter,Arial,Helvetica,sans-serif; font-size:11px; color:#888888;">
                © {html.escape(site_name)}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=from_email,
        to=[email],
    )
    msg.attach_alternative(html_message, "text/html")
    msg.send(fail_silently=False)
