# coLEX Reviews

Challenge format (brief §6.3, mandatory):

```
[ID] [Severity: Critical|Major|Minor] [Area] [Reviewer]
Claim: what is wrong
Evidence: file:line, failing test, log excerpt, or official text citation
Proposed fix: concrete change
Builder response: ACCEPT (commit) | REJECT (reason) | DEFER (to stretch, reason)
Orchestrator ruling: ...
```

Critical findings block the gate. Major findings must be fixed or explicitly deferred by the orchestrator. Minor findings are optional.

Independence note (D-010, open): this build session cannot dispatch a separate Code Breaker. Until the humans rule on D-010, no branch is merged to `main` on the strength of a same-session review. Any same-session check recorded here is labeled as such and does not count as the pre-merge review.

## Pre-merge review log

One line per merged branch: branch, reviewer role, what was checked, result.

## Findings
