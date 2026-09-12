# API guide

Tradefog exposes its REST API under `/api/v1`. Use `/docs` for interactive
requests and `/openapi.json` for the generated contract. The introduction in
Swagger describes authentication, decimal values, pagination, PATCH and error
envelopes. Types, required fields, limits and route parameters come from that
contract; this guide covers how to use the operations together.

## Journal workflow

Select a profile before creating or editing journal trades. Trade endpoints
live under `/profiles/{profile_id}/trades`, including preparation, lifecycle
actions and attachments. The profile comes from the path, never from the
creation body. Attachment content URLs include both the profile and trade.
The server checks the entire hierarchy; an inaccessible or mismatched
resource returns `404`.

`GET /trades` and `GET /analytics` provide owner-wide read-only overviews,
with optional profile filters. Profile-specific analytics lives at
`GET /profiles/{profile_id}/analytics`. Both variants use the same calculations;
analytical trajectory points include `profile_id` for direct trade links.
Profile-specific list and analytics endpoints do not accept a profile query
filter. Venue capabilities and public market data remain under `/venues`.

Swagger groups profile resources under consistently ordered `Profiles · …`
tags and puts aggregate reads under `Overview · …`. Each operation has one
tag. Backend and frontend must be released together: former root trade-detail,
trade-write and attachment URLs are no longer supported. Existing records and
stored image files need no migration.

1. Authenticate with `/auth/token`. In Swagger, use **Authorize**, enter the
   account credentials and leave client ID and secret empty. Accounts are
   provisioned through the CLI. See [authentication](architecture.md#authentication-and-profile-api)
   for token lifetime and password-change behavior.
2. Create a profile for a manual venue or Bybit. Add manual instruments or
   import selected Bybit instruments. Import resolves the profile's asset
   identities; browsing `/venues` does not create journal records.
3. Record deposits in profile assets. Create a strategy and allocate capital
   in its settlement asset. Allocations commit capital; they are not ledger
   withdrawals.
4. Create a draft trade, record preparation and ATR, and preview a position.
   Save entry and stop before submitting. Saving the plan replaces both
   anchors: missing or null values clear them. Preview does not save the plan
   or reserve funds, and submission checks current capital again.
5. Submit as `pending_entry` or `open`. Submission freezes the financial
   snapshot and reserves funds. Open a pending trade when the external order
   fills. Close an open trade with signed net P&L, then complete its review.
   Cancellation releases reservations for draft, pending or open trades.

These actions record decisions and accounting facts. They do not place orders
or transfer exchange funds. See [domain model](domain-model.md) for domain
rules and [analytics](analytics.md) for metric definitions.

## Money and capital

Use decimal strings in clients and preserve their precision. A displayed
example such as `"1000.00"` does not require exactly two decimal places.
Request schemas describe the precision and bounds accepted by each field.

All asset balances use that asset's units:

| Field         | Meaning                                                    |
| ------------- | ---------------------------------------------------------- |
| `balance`     | Signed wallet entries plus net P&L from closed trades      |
| `allocated`   | Capital in non-archived strategy allocations               |
| `reserved`    | Asset amounts reserved by pending and open trades          |
| `available`   | `balance - reserved`                                       |
| `uncommitted` | `balance - max(allocated, reserved)`, used for withdrawals |

Reservations can fund a position, inventory or a loss buffer; they are not
synonymous with planned trade risk. Archive state and financial status are
separate. The `risk_stop_capital` floor produces an advisory `risk_stopped`
status when the balance reaches or falls below it.

Deposit and withdrawal requests both use positive amounts. Ledger responses
represent withdrawals as negative amounts. Only operation notes can be
edited; amounts and kinds remain immutable.
The operation-note PATCH replaces the note: an omitted or null note clears
the current text, unlike metadata PATCH operations that retain omitted fields.

Closing a trade takes net `realized_pnl` in its settlement asset. Include fees
and funding in that number yourself. `total_commission` and `funding_result`
provide context and are not applied to the net result again.

## Handling rejected actions

Read `detail.code` for application errors. Validation failures instead expose
an array at `detail`, with locations and messages for invalid inputs. Do not
assume every failure has the same envelope; authentication middleware may
return a string detail.

| Response                        | Client action                                                           |
| ------------------------------- | ----------------------------------------------------------------------- |
| `401`                           | Refresh or obtain credentials before another authenticated request      |
| `404`                           | Treat the requested journal resource as unavailable to this user        |
| `409`                           | Reload state and resolve the conflicting balance, identity or lifecycle |
| `422`                           | Correct fields or operation-specific prerequisites                      |
| Market error with `Retry-After` | Wait the indicated number of seconds                                    |

For example, `missing_draft_plan` requires saving entry and stop;
`manual_atr_required` requires supplying an ATR value; `invalid_mode` requires
matching the instrument request to its profile venue. Error messages explain
state conflicts without exposing database internals. A lost response does not
prove a mutation failed: inspect journal state before repeating it.

## Maintaining documentation

- Keep operation intent, prerequisites, side effects and actionable failures
  in endpoint docstrings; FastAPI exposes them in OpenAPI.
- Use field descriptions for units, signs, null semantics and distinctions
  that names and types cannot explain. Do not repeat obvious names or limits.
- Keep a few coherent object examples in `api/documentation.py`, referenced
  by schemas. Use examples for related values and unfamiliar request shapes;
  do not annotate every decimal field just to influence Swagger's generator.
- Keep shared transport conventions in the API introduction, workflows here,
  and formulas and architecture in their dedicated documents. Update the
  relevant source when behavior changes.
- Examples are metadata, never field defaults. Do not change validators,
  decimal serialization or generated schema types to improve sample output.
  Avoid custom OpenAPI rewriting and documentation-only domain types.
