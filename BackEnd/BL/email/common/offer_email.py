import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from ReqRes.common.send_offer_schemas import SendOfferReq

logger = logging.getLogger(__name__)


def send_offer_email(details: SendOfferReq):
    logger.info(f"Starting email send process for property: {details.property_address}")
    logger.info(f"Recipient: {details.agent_email} (Agent: {details.agent_name})")

    sender_email = "BigWhalesLLC@gmail.com"
    sender_password = os.getenv("EMAIL_PASSWORD")

    if not sender_password:
        logger.error("EMAIL_PASSWORD environment variable is not set")
        return False, "Email password not configured"

    # Strip any whitespace (common issue when copying/pasting)
    sender_password = sender_password.strip()

    if len(sender_password) != 16:
        logger.warning(f"Email password length is {len(sender_password)} (expected 16 for Gmail App Password)")

    logger.info(f"Email password found (length: {len(sender_password)})")
    logger.info(f"Email password starts with: {sender_password[:2]}... (masked for security)")

    subject = f"Cash Offer for {details.property_address}"
    logger.info(f"Email subject: {subject}")

    body = f"""
<html>
  <head>
    <style>
      body {{
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        color: #2c3e50;
        line-height: 1.7;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        margin: 0;
        padding: 40px 20px;
      }}
      .container {{
        max-width: 650px;
        margin: 0 auto;
        background-color: #ffffff;
        padding: 45px;
        border-radius: 12px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.15);
        border-top: 6px solid #3498db;
      }}
      .greeting {{
        font-size: 18px;
        color: #2c3e50;
        margin-bottom: 20px;
        font-weight: 500;
      }}
      .intro {{
        font-size: 16px;
        color: #34495e;
        margin-bottom: 25px;
      }}
      .highlight {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 25px 30px;
        border-radius: 10px;
        margin: 30px 0;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
      }}
      .highlight p {{
        margin: 12px 0;
        font-weight: 600;
        font-size: 16px;
        color: #ffffff;
        line-height: 1.8;
      }}
      .highlight p:first-child {{
        font-size: 20px;
        font-weight: 700;
        margin-bottom: 18px;
        padding-bottom: 15px;
        border-bottom: 2px solid rgba(255,255,255,0.3);
      }}
      .highlight a {{
        color: #ffffff;
        text-decoration: underline;
        font-weight: 600;
      }}
      .cta {{
        font-size: 17px;
        color: #2c3e50;
        font-weight: 600;
        margin: 30px 0;
        text-align: center;
        padding: 15px;
        background-color: #ecf0f1;
        border-radius: 8px;
      }}
      .footer {{
        margin-top: 45px;
        padding: 35px;
        background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
      }}
      .footer p {{
        margin: 8px 0;
        font-size: 20px;
        color: #ffffff;
        font-weight: 600;
      }}
      .footer-name {{
        font-size: 24px !important;
        font-weight: 700 !important;
        margin-bottom: 15px !important;
        letter-spacing: 0.5px;
      }}
      .footer-contact {{
        font-size: 18px !important;
        font-weight: 500 !important;
        margin: 10px 0 !important;
      }}
      .footer a {{
        color: #3498db;
        text-decoration: none;
        font-weight: 600;
        font-size: 18px;
      }}
      .footer a:hover {{
        color: #5dade2;
        text-decoration: underline;
      }}
      a {{
        color: #3498db;
        text-decoration: none;
        font-weight: 600;
      }}
      a:hover {{
        color: #2980b9;
        text-decoration: underline;
      }}
      strong {{
        color: #2c3e50;
        font-weight: 700;
      }}
    </style>
  </head>
  <body>
    <div class="container">
      <p class="greeting">Hi {details.agent_name},</p>
      <p class="intro">I’m writing to you regarding the property at <strong>{details.property_address}</strong></p>
      <p class="intro">We are local investors purchasing under our entity, Big Whales AY LLC. (<a href="https://drive.google.com/file/d/1HxskELeQFfljFngV5OFvjuhDeUbQ1Dyx/view">LLC Formation</a>)</p>

      <p class="intro">I have structured an offer to eliminate risks for the seller. I am offering a clean, fast closing:</p>

      <div class="highlight">
        <p>Purchase Price: ${details.purchase_price:,.2f}</p>
        <p>Terms: 100% - Hard Money (No Financing Contingency) (<a href="https://drive.google.com/file/d/1uP2FbFpFc5SVHWBdVcBCoAfhBijTzyBP/view">PreApproval</a>)</p>
        <p>Inspection: {details.inspection_period_days}-Day inspection period - We are purchasing "As-Is" and will not ask for repairs.</p>
        <p>Closing: 14 Days (or sooner if title is ready)</p>
        <p>Earnest Money: $5,000 can be wired as soon as today</p>
        <p>Other Contingencies: None</p>
      </div>

      <p class="cta">We are ready to sign and get this moving today.</p>

      <div class="footer">
        <p class="footer-name">Yarden Kelly - Big Whales AY LLC</p>
        <p class="footer-contact">(786)-600-7210</p>
        <p class="footer-contact"><a href="mailto:BigWhalesLLC@gmail.com">BigWhalesLLC@gmail.com</a></p>
      </div>
    </div>
  </body>
</html>
    """

    logger.info("Creating email message")
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = details.agent_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))
    logger.info("Email message created successfully")

    try:
        logger.info("Connecting to SMTP server (smtp.gmail.com:465)")
        # Using Gmail's SSL port 465
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        logger.info("SMTP connection established")

        logger.info("Attempting to login to SMTP server")
        server.login(sender_email, sender_password)
        logger.info("SMTP login successful")

        logger.info(f"Sending email to {details.agent_email}")
        server.send_message(msg)
        logger.info("Email sent successfully")

        server.quit()
        logger.info("SMTP connection closed")
        return True, "Email sent successfully"
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication Error: {e}")
        logger.error(f"Error code: {e.smtp_code}, Error message: {e.smtp_error}")
        return False, f"Authentication failed: {str(e)}"
    except smtplib.SMTPException as e:
        logger.error(f"SMTP Error: {e}")
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error sending email: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False, f"Error sending email: {str(e)}"
