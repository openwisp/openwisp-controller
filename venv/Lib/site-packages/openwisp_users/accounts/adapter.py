from allauth.account.adapter import DefaultAccountAdapter
from django.contrib.sites.shortcuts import get_current_site
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from openwisp_utils.admin_theme.email import send_email


class EmailAdapter(DefaultAccountAdapter):
    def send_mail(self, template_prefix, email, context):
        if "current_site" not in context and hasattr(self, "request"):
            context["current_site"] = get_current_site(self.request)
        subject = render_to_string("{0}_subject.txt".format(template_prefix), context)
        subject = " ".join(subject.splitlines()).strip()
        subject = self.format_email_subject(subject)
        content = {}
        errors = {}
        for ext in ["html", "txt"]:
            template_name = "{0}_message.{1}".format(template_prefix, ext)
            if "activate_url" in context:
                context["call_to_action_url"] = context["activate_url"]
                context["call_to_action_text"] = _("Confirm")
            try:
                template_name = "{0}_message.{1}".format(template_prefix, ext)
                content[ext] = render_to_string(
                    template_name, context, self.request
                ).strip()
            except TemplateDoesNotExist as e:
                errors[ext] = e
            text = content.get("txt", "")
            html = content.get("html", "")
            # both templates fail to load, raise the exception
            if len(errors.keys()) >= 2:
                raise errors["txt"] from errors["html"]
        send_email(subject, text, html, [email], context)
