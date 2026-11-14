> FICTIONAL – PayRo SRL is a fabricated company for the coLEX demo

# Service Architecture

Status: active

## Services and providers
| Service | Provider | Code |
|---|---|---|
| Platform hosting and document storage | AWS | `payments/providers.py` |
| One-time passwords | SMSNord | `payments/providers.py` |
| Identity verification | VerifID | `payments/providers.py` |
| Core ledger | LedgerCore | `payments/providers.py` |
| Card top-ups | CardAxis | `payments/providers.py` |
| Payee name check (pilot) | NameMatch | `payments/providers.py` |

## Transfer flow
The app calls `authorize_transfer()` in `payments/transfer.py`, which checks the one-time password and computes the fee from `payments/fees.yaml`.
