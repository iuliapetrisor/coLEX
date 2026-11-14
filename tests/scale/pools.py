"""Everything the generator draws from: the vocabulary and the document kinds (all invented)."""
from tests.scale.kinds_work import WORK
from tests.scale.vocab import (COMPLAINTS, FEATURES, HR_TOPICS, LABEL, MONTHS, PEOPLE, PROVIDERS,  # noqa: F401
                               SYMPTOMS, SYSTEMS)

OFFICE = {
    "finance": {"weight": 6, "source": "onedrive", "folder": "finance", "title": ["Month-end close notes, {month}"],
                "sections": {"Notes": [
                    "Ledger balances were reconciled against the bank statements.",
                    "Two supplier invoices were booked late.", "Bookkeeping entries for card top-ups were corrected.",
                    "Open items are tracked in the finance tracker.", "The invoice from {provider} is still missing.",
                    "Prepared by {person}."]}},
    "risk": {"weight": 4, "source": "onedrive", "folder": "risk", "title": ["Risk assessment: {system}"],
             "sections": {"Assessment": [
                 "The risk register entry for the {system} was reviewed.", "Likelihood stays low; impact is medium.",
                 "Risk assessment owner: {person}.", "The next review is in six months.",
                 "No new control is proposed."]}},
    "support": {"weight": 5, "source": "onedrive", "folder": "support", "title": [
        "Complaint handling summary, week {week}"], "sections": {"Summary": [
            "{count} complaints were received; most were about {complaint}.", "Each complaint has a support ticket.",
            "Answer templates were updated.", "The oldest open complaint is nine days old.",
            "Prepared by {person} for the weekly review."]}},
    "hr": {"weight": 10, "source": "intranet", "folder": "hr", "title": ["Policy: {topic}"], "sections": {"Rules": [
        "Employees may work from home two days per week; desks are shared.",
        "Parental leave is requested through the HR portal.", "Visitors sign in at reception.",
        "A medical certificate is needed for sick leave longer than three days.", "Ask your line manager first.",
        "Questions go to {person} in HR."]}},
    "product": {"weight": 12, "source": "gdrive", "folder": "product", "title": ["Product brief: {feature}"],
                "sections": {"Brief": [
                    "Goal: fewer support contacts about {feature}.", "Customers asked for this in the last survey.",
                    "The instant path already runs around the clock.",
                    "Onboarding takes too many steps today (KYC photos).", "No change to fees is planned.",
                    "Success metric: weekly active customers.", "Owner: {person}."]}},
    "news": {"weight": 3, "source": "intranet", "folder": "news", "title": ["Company update, {month}"],
             "sections": {"News": [
                 "The summer party is on the last Friday of the month.", "Welcome to our new colleagues.",
                 "The quarterly all-hands is next week.", "The bike shed has moved to the back entrance.",
                 "Thanks to everyone who helped with the release."]}},
}
KINDS = {**WORK, **OFFICE}
