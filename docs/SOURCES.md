# Sources

## Official legal texts (`sandbox/feed/`)

Every file in `sandbox/feed/` is an excerpt of an act published in the Official Journal of the European Union, copied verbatim by `tools/fetch_law.py` from the Publications Office (`http://publications.europa.eu/resource/celex/<CELEX>`, English XHTML). Nothing is paraphrased or generated. Each file records its CELEX number, official title, EUR-Lex URL, publication date, retrieval date, the articles kept, whether the excerpt is complete, and a SHA-256 of the excerpt.

- The only edits are mechanical: HTML tags removed, whitespace normalised, a point marker such as `(a)` joined to its text, and a `## Article N` heading added per article. An article quoted inside an amending article is labelled `[inserted by Article N]`; that label is ours, not part of the official text.
- Only the Official Journal version is authentic. These excerpts are for a demo; check EUR-Lex before relying on them.
- Reuse: to our understanding, EUR-Lex content may be reused with acknowledgement of the source (© European Union, https://eur-lex.europa.eu). We have not had this checked by a lawyer.

| CELEX | Role in the demo |
|---|---|
| 32022R2554 | DORA. Articles 2, 19, 28, 30, 64 (excerpt). Relevant: Art. 2(1)(b) lists payment institutions. |
| 32025R0301 | Delegated Regulation on the content and time limits of major ICT incident reports (complete). Relevant. |
| 32024R0886 | Instant Payments Regulation (complete). Relevant. |
| 32023R1114 | MiCA, Articles 1–2 (excerpt). Distractor: PayRo provides no crypto-asset services. |
| 32025R0150 … 32025R0220 (19 acts) | Distractors: plant protection, feed additives, residues, animal disease control, a geographical indication, tariff quotas, maritime fuel verifiers, renewable-energy certification, fishing opportunities, trade preferences, insurer technical provisions, customs, the Ukraine Facility. |

Acts deliberately left out as distractors because they could apply to a payment institution: sanctions regulations (32025R0190, 32025R0206) and a correction to a PSD2 technical standard (32025R0212).

Facts used in the build and where the official text states them:

| Fact | Source |
|---|---|
| DORA applies from 17 January 2025 | 32022R2554 Art. 64 |
| Payment institutions are in scope of DORA | 32022R2554 Art. 2(1)(b) |
| Data location is a clause for all ICT contracts; audit rights and exit strategies only for contracts supporting critical or important functions | 32022R2554 Art. 30(2)(b), 30(3)(e), 30(3)(f) |
| Initial notification within 4 hours of classification and no later than 24 hours from awareness; intermediate report within 72 hours of the initial notification; final report within one month of the latest intermediate report | 32025R0301 Art. 5(1) |
| PSPs in a non-euro Member State: equal charges by 9 January 2027 | 32024R0886 Art. 1, inserted Art. 5b(3) of Regulation (EU) No 260/2012 |
| PSPs in a non-euro Member State: verification of payee by 9 July 2027 | 32024R0886 Art. 1, inserted Art. 5c(9) |
| Payment institutions in a non-euro Member State: receive instant euro credit transfers by 9 April 2027, send by 9 July 2027 | 32024R0886 Art. 1, inserted Art. 5a(8) |

Not verified: the Compliance.ai study numbers and the Romanian VAT law dates quoted in brief §1.1. Do not use them in the pitch until someone locates the primary sources.

## PayRo SRL

PayRo SRL and every file under `sandbox/` other than `sandbox/feed/` are fabricated for the demo. Provider names other than Amazon Web Services are invented.
