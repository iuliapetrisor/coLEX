"""Vocabulary of the generated company documents for the scale test. Everything here is invented.

The documents talk about the same subjects as the sandbox (transfers, fees, incidents, providers), so they
are not trivially off-topic, but they are written not to state a rule of their own.
"""

LABEL = "> FICTIONAL – PayRo SRL is a fabricated company for the coLEX demo"
SYSTEMS = ["card top-up service", "notification service", "statement export", "mobile app login", "ledger sync job",
           "onboarding flow", "support console", "exchange-rate feed", "receipt generator", "admin back office",
           "transfer queue", "balance cache", "document storage", "audit log shipper", "session service"]
SYMPTOMS = ["times out under load", "shows a stale value", "sends duplicate messages", "fails on retry",
            "rejects valid input", "is slow on Monday mornings", "logs too much", "loses its settings on restart"]
PEOPLE = ["Ioana", "Radu", "Elena", "Mihai", "Andreea", "Vlad", "Cristina", "Bogdan", "Daria", "Tudor"]
PROVIDERS = ["AWS", "SMSNord", "LedgerCore", "CardAxis", "VerifID"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
FEATURES = ["instant transfers on weekends", "payee's name hints", "faster onboarding", "top-up limits",
            "statement export", "dark mode", "spending insights"]
HR_TOPICS = ["remote work", "parental leave", "travel expenses", "training budget", "visitors and badges",
             "sick leave", "desk booking"]
COMPLAINTS = ["a delayed card top-up", "a missing statement", "a blocked login", "a slow refund", "an unclear receipt"]
COMMENTS = ["{date2}, {person}: moved to the next sprint.", "{date2}, {person}: cannot reproduce on staging.",
            "{date2}, {person}: fixed in the next release.", "{date2}, {person}: waiting for a recording from support.",
            "{date2}, {person}: duplicate of an older ticket, linked."]
TICKET = "Type: {tickettype} · Status: {status} · Created: {date}"
