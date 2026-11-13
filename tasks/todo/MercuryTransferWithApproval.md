# MercuryTransferWithApproval: Deposit and Steal through Mercury's approval-gated transfer

The transfer token is a custom token with only "Transfer Money with Approval" (no immediate-transfer scope exists for
custom tokens, and an approval in Mercury keeps a leaked token from moving money alone). The app called the immediate
`POST /api/v1/transfer`, which that token is not allowed to use (403). Quick change, no new tests (as asked).

- [x] Call `POST /api/v1/request-transfer` (same body, per Mercury's docs); read its answer (id, `pendingApproval` / `approved` / `rejected` / `cancelled`) (10 min)
- [x] New outcome `waiting_for_approval_in_mercury`: not counted; matched to the bank transaction once Mercury sends it, then counted from the feed once (10 min)
- [x] The transfer window and the card say "approve it in Mercury" (5 min)
- [x] Golden update commit for the new outcome value (5 min)
- Tests: none added; the existing transfer tests pass (the client test's URL updated with the endpoint).
- MCP: unchanged (deposit and steal are not tools).
- Security (`.claude/security.md`): a narrower token (approval needed); nothing new stored or shown.
- Not done: a rejected or cancelled request is not read back from Mercury; it stays "Approve it in Mercury" on the card.
