import logging
from smtplib import SMTPRecipientsRefused

from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from . import settings as app_settings

logger = logging.getLogger(__name__)


def send_email(
    subject,
    body_text,
    body_html,
    recipients,
    extra_context=None,
    html_email_template="openwisp_utils/email_template.html",
    **kwargs,
):
    extra_context = extra_context or {}
    mail = EmailMultiAlternatives(
        subject=subject,
        body=strip_tags(body_text),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
        **kwargs,
    )
    if app_settings.OPENWISP_HTML_EMAIL and body_html:
        site = get_current_site(None)
        scheme = "http" if settings.DEBUG else "https"
        context = dict(
            title=subject,
            message=body_html,
            site_name=site.name,
            site_url=f"{scheme}://{site.domain}",
            logo_url=app_settings.OPENWISP_EMAIL_LOGO,
            recipients=", ".join(recipients),
        )
        context.update(extra_context)

        html_message = render_to_string(
            html_email_template,
            context=context,
        )
        mail.attach_alternative(html_message, "text/html")
    try:
        mail.send()
    except SMTPRecipientsRefused as err:
        logger.warning(f"SMTP recipients refused: {err.recipients}")
