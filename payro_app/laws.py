"""Demo notes shown under the PayRo app: which official text each scenario comes from.

Every string in `quotes` is copied from the official excerpt stored in sandbox/feed; a test checks that
each one is a verbatim substring of that file. `plain` is our own summary, not legal text.
"""

NOTES = {
    "fees": {
        "celex": "32024R0886",
        "where": "Regulation (EU) 2024/886, Article 1, inserting Article 5b into Regulation (EU) No 260/2012",
        "quotes": [
            "Any charges levied by a PSP on payers and payees in respect of sending and receiving instant credit "
            "transfers shall not be higher than the charges levied by that PSP in respect of sending and receiving "
            "other credit transfers of corresponding type.",
            "PSPs located in a Member State whose currency is not the euro shall comply with this Article by "
            "9 January 2027.",
        ],
        "plain": "An instant euro transfer may not cost more than a standard one. PayRo is in a Member State whose "
                 "currency is not the euro, so its date is 9 January 2027.",
    },
    "payee": {
        "celex": "32024R0886",
        "where": "Regulation (EU) 2024/886, Article 1, inserting Article 5c into Regulation (EU) No 260/2012",
        "quotes": [
            "The payer’s PSP shall perform the service ensuring verification immediately after the payer provides "
            "relevant information about the payee and before the payer is offered the possibility of authorising "
            "that credit transfer.",
            "Where they do not match, the payer’s PSP shall, based on information provided by the payee’s PSP, "
            "notify the payer thereof and inform the payer that authorising the credit transfer might lead to "
            "transferring the funds to a payment account not held by the payee indicated by the payer.",
            "PSPs shall ensure that the performance of the service ensuring verification and of the service "
            "described in paragraph 2 does not prevent payers from authorising the credit transfer concerned.",
            "PSPs located in a Member State whose currency is not the euro shall comply with this Article by "
            "9 July 2027.",
        ],
        "plain": "Before the customer can authorise, the app must check that the name matches the account and say so "
                 "if it does not. The customer may still go ahead.",
    },
    "incident": {
        "celex": "32025R0301",
        "where": "Commission Delegated Regulation (EU) 2025/301, Article 5(1)",
        "quotes": [
            "within four hours from the classification of the ICT-related incident as a major ICT-related incident "
            "and no later than 24 hours from the moment the financial entity has become aware of the ICT-related "
            "incident",
            "at the latest within 72 hours from the submission of the initial notification",
            "no later than one month after either the submission of the intermediate report",
        ],
        "plain": "A major ICT incident needs an initial notification, an intermediate report and a final report, each "
                 "with its own time limit.",
    },
}
