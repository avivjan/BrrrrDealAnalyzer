# MercuryTransferRefusalReason: say why Mercury refused an in-app transfer

A Deposit came back "Mercury refused the transfer. Nothing was sent." with no reason anywhere (not in the answer, not in
the logs). Quick addition, no new tests (as asked).

- [x] Keep Mercury's HTTP status on a refused transfer (`mercury_refusal_http_status`), log the status code only (never Mercury's text) (10 min)
- [x] Answer it on the transfer; the transfer window explains it (401/403 the token's permissions or allowed IPs, 400/422 the request, 429 slow down); the card shows the code (10 min)
- [x] Snapshot goldens in a `Golden update:` commit (5 min)
- Tests: none added, by request; the existing transfer tests pass.
- MCP: no new tool (the field rides on the existing status answer).
- Security (`.claude/security.md`): only a status code is stored and shown, never Mercury's response text; no token or secret touched.
