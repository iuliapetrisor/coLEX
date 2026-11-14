"""Generated document kinds, part 1: tickets and engineering pages.

kind -> where it lives, how it is titled, and the sentences its sections are drawn from.
"""
from tests.scale.vocab import COMMENTS, TICKET

WORK = {
    "ticket-pay": {"weight": 22, "source": "jira", "folder": "PAY", "file": "PAY-{num}", "head": TICKET, "title": [
        "Instant transfer receipt {symptom}", "One-time password screen {symptom}", "Fee line on the receipt {symptom}",
        "Payee's name field {symptom}", "The {system} {symptom}"], "sections": {"Description": [
            "Reported by {person} from support after two customers called.",
            "The {system} {symptom}; a restart clears it for a few hours.",
            "Seen on the instant SEPA path only; other transfers look fine.",
            "The one-time password arrives, but the screen does not move on.",
            "The fee line is rendered twice on small screens.",
            "Steps to reproduce are in the attached recording.",
            "Likely a regression from the last release of the {system}.",
            "{provider} confirmed that nothing changed on their side."], "Comments": COMMENTS}},
    "ticket-ops": {"weight": 10, "source": "jira", "folder": "OPS", "file": "OPS-{num}", "head": TICKET, "title": [
        "Incident: the {system} {symptom}", "Outage of the {system}"], "sections": {"Description": [
            "{provider} had a short outage; the {system} recovered on its own.",
            "On-call was paged and followed the runbook.", "No customer data was affected.",
            "The incident lasted about {minutes} minutes.", "Monitoring caught it before customers did.",
            "A follow-up task was opened for the alert threshold."], "Comments": COMMENTS}},
    "ticket-sup": {"weight": 8, "source": "jira", "folder": "SUP", "file": "SUP-{num}", "head": TICKET, "title": [
        "Customer complaint about {complaint}"], "sections": {"Description": [
            "The customer wrote to support about {complaint}.", "The support ticket was answered the same day.",
            "The complaint was closed after a call.", "No refund was requested.",
            "The customer asked for a written answer."], "Comments": COMMENTS}},
    "eng": {"weight": 12, "source": "confluence", "folder": "ENG", "title": [
        "Runbook: {system}", "Design note: {system}", "Release notes: {system}, {month}"], "sections": {"Overview": [
            "The {system} runs in the eu-central-1 region on shared hosting.",
            "Settings live in the service repository; secrets are in the vault.",
            "It calls the {provider} API through the provider integration layer.",
            "Dashboards show request rate, errors and latency.", "To roll back, redeploy the previous image.",
            "Architecture: one stateless service and one queue.", "Owner on call this quarter: {person}."]}},
    "postmortem": {"weight": 8, "source": "confluence", "folder": "OPS", "title": [
        "Postmortem: the {system} {symptom}"], "sections": {"Summary": [
            "Summary of the incident and what we changed afterwards.", "The outage lasted about {minutes} minutes.",
            "Root cause: a settings change that was not reviewed.", "Action: add an alert on queue depth.",
            "{provider} was not involved.", "Customers saw errors in the app during that time."]}},
}
