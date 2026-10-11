# ArvEstimateWithClaude: "Estimate ARV with Claude" popup for BRRRR and FLIP

Branch: `claude/admiring-fermi-pqek7t` (session-designated; wins over CLAUDE.md's `<task_name>` rule, as on previous
tasks). Plan file on the branch: `tasks/todo/ArvEstimateWithClaude.md` (mirrors this plan, checkable, with
estimates). Per CLAUDE.md the plan is checked in with the user before implementation code.

## Context

Today the ARV (BRRRR, `arv_in_thousands`) and the Projected Sale Price (FLIP, `salePrice`) are typed in by hand.
The user runs a long comps prompt in claude.ai and copies the number back. The goal is a button next to those
fields that opens a popup. There the user confirms the address and writes a note about the situation. The backend
sends a strategy-specific prompt to Claude with live web search and gets back JSON in a fixed template. The popup
renders it (range, target, confidence, comps table, average DOM, logic), and an **Apply** button writes the numbers
into the form.

User decisions (asked and answered):
- The backend calls the Claude API.
- Fields change only when the user clicks **Apply**.
- The estimate lives only in the popup: nothing is persisted and there is no migration.

Two strategies, two valuation lenses:
- **FLIP: conservative, the market lens.** The buyer is a retail buyer and the risk is real. Any credible
  renovated sale below the cluster pulls the target down. The target sits toward the lower part of the adjusted
  range, never above the median. The answer must report the average and median DOM of the sold comps plus a pace
  verdict (fast / normal / slow) so the user can feel the submarket.
- **BRRRR: the appraisal lens.** You only need 3–4 strong comps that an appraiser would pick: ≤1 mi (widen only if
  needed), ≤6 mo, GLA ±20%, same style and bed count, renovated. Weaker or outlier comps are listed but don't drag
  the target down. The answer also returns a `conservative_lowest_arv` for the existing "Lowest ARV Possible
  (stress test)" field.

## Design

### Backend
- **Dependency:** pin `anthropic==<latest>` in `BackEnd/requirements.txt` (exact pin per F-16, `pip-audit` clean).
- **Schemas:** `BackEnd/ReqRes/common/arv_estimate_schemas.py`, re-exported from `ReqRes/arvEstimate/` like
  `ReqRes/email/sendOffer`.
  - `ArvEstimateReq` has these fields:
    - `deal_type: Literal["BRRRR","FLIP"]`
    - `property_address: str` (1–300 chars)
    - `investor_situation_note: str` (0–2000 chars)
    - optional subject facts the form already has: `subject_square_feet`, `subject_bedrooms`,
      `subject_bathrooms`, `purchase_price`, `rehab_budget`. These are sent so Claude can match GLA and beds.
  - `ArvEstimateRes` is the template Claude must fill. The same Pydantic model is the
    `output_config.format` JSON schema and the response model. It has these fields:
    - `estimated_arv_range_low`, `estimated_arv_range_high`, `target_arv`, `conservative_lowest_arv`
    - `confidence_score_1_to_10`
    - `average_days_on_market_of_sold_comps`, `median_days_on_market_of_sold_comps`,
      `market_pace_verdict` (`fast|normal|slow`)
    - `market_logic`
    - `subject_property_as_found` (beds/baths/sqft/year built/lot that Claude found)
    - `sold_comparables[]`, `active_or_pending_comparables[]`
    - `discarded_comparables[]` (address + reason)
    - `data_caveats[]`, `source_urls[]`
  - Each comparable (`ArvComparableProperty`) has these fields:
    - address, distance_from_subject_in_miles, listing_status, sale_or_list_date, sale_or_list_price
    - bedrooms, bathrooms, square_feet, year_built, lot_size_square_feet
    - price_per_square_foot, days_on_market, renovation_condition
    - adjusted_value, adjustment_explanation, weight_in_valuation (`primary|supporting|excluded`), source_url
- **Prompt:** `BackEnd/BL/arvEstimate/common/arv_estimate_prompts.py`, `build_arv_estimate_prompt(req)`. It is the
  user's prompt, improved:
  - shared sections: role, data retrieval (3–5 sold within 6 mo / 1 mi, 2 active/pending, flip-grade only), the
    comparison matrix, adjustments (bed, bath, ±GLA, lot, weighting by recency and GLA closeness)
  - a strategy section (FLIP or BRRRR, as above)
  - "use web_search on Zillow/Redfin/Realtor; never invent a comp; null when unknown; lower confidence when comps
    are thin"
  - an output section that points at the JSON template
  - the user's note goes inside `<investor_situation_note>` tags, framed as context and not as instructions
    (prompt-injection hygiene)
- **Claude client:** `BackEnd/BL/arvEstimate/common/anthropic_arv_client.py`.
  - Credentials: `ANTHROPIC_API_KEY` wrapped in `BL/common/secret.Secret`.
  - Request: model `claude-opus-5-5` (env `ARV_ESTIMATE_MODEL` overrides) with `output_config={"effort":"high",
    "format":{json_schema}}` and tool `{"type":"web_search_20260209","name":"web_search","max_uses":15}`.
  - Server-side refusal fallback: `betas=["server-side-fallback-2026-07-01"], fallbacks="default"`.
  - Call: streamed with `.get_final_message()`. On `pause_turn` it resends `[user, assistant(content)]`, up to 5
    times. `refusal` maps to a clear error.
  - Parsing: the last text block is parsed with `ArvEstimateRes.model_validate_json`.
  - Post-checks: drop non-`http(s)` URLs, and keep `low ≤ target ≤ high` and `conservative_lowest_arv ≤ target`.
- **Orchestrator:** `BackEnd/BL/arvEstimate/estimateArv.py`.
- **Router:** `BackEnd/routers/arv_estimate.py`, `POST /arv-estimate`, modelled on `routers/email.py`.
  - Rate limit: `count_recent("arv_estimate", 60, ip=…)` against `ARV_ESTIMATE_PER_HOUR` (default 20), else 429.
  - Each call is audited with `{ok, deal_type}` only.
  - Errors: 503 "ARV estimate is not configured" when the key is unset. 502 with a ref id on upstream or parse
    failure, and the exception text is never echoed.
  - Wiring: appended at the end of `routers/__init__.py:ALL_ROUTERS`, so it is gated by app key + session like
    every data route.
- **Env:** add `ANTHROPIC_API_KEY=`, `ARV_ESTIMATE_PER_HOUR=20`, `ARV_ESTIMATE_MODEL=` to `.env.example` and the
  README env section. Make sure `install_secret_redaction` covers the key.

### MCP server support
`mcp_server.py` already turns every route into a tool, so `arv_estimate` appears automatically.
- Add it to `OPEN_WORLD_TOOLS` (it searches the web and spends API credit). It is not destructive.
- `MCP_SCOPES` gating works unchanged.
- Tests cover it (below).

### Frontend
- **Types:** `frontend/src/types/arvEstimate.ts` mirrors the schemas.
- **API:** `estimateArvWithClaude(req)` in `frontend/src/api/index.ts`, same shape as `sendOffer`, with a 180 s
  per-request timeout.
- **Popup:** `frontend/src/components/deal/ArvEstimateWithClaudePopup.vue` on `UiModalPanel`, following the
  `SendOfferModal.vue` field and footer pattern.
  - Inputs: Address (prefilled from `deal.address`, editable, required), a "Situation note" textarea, and the
    strategy shown read-only. **Estimate ARV** button.
  - Loading state: `UiSkeleton` + "Claude is pulling comps, usually 30–90 s".
  - Result:
    - KPI tiles (`UiStatTile`): Target ARV, Range, Confidence /10, Avg DOM + pace, and for BRRRR only the
      Conservative lowest ARV.
    - Sold comps table and Active/Pending table (`UiDataTable`), with primary comps marked.
    - Market logic, caveats, discarded comps, and source links (`target=_blank rel="noopener noreferrer"`, all
      text through Vue escaping, no `v-html`).
  - Error state shows the backend `detail`.
  - **Apply** emits `apply-arv-estimate`:
    - BRRRR: `arv_in_thousands = target/1000`, `lowestArv = conservative/1000`
    - FLIP: `salePrice = target/1000`
    - The thousands convention is confirmed against `MoneyInput :inThousands` during implementation.
- **Button:** a small "Estimate with Claude" button (`data-testid="form.action.estimateArvWithClaude"`).
  - BRRRR: next to the ARV field in `components/deal/brrr/RefinanceSection.vue`, which emits
    `open-arv-estimate`.
  - FLIP: next to `salePrice` in `DealInputsForm.vue`.
  - `DealInputsForm.vue` owns the popup and applies the values through its existing `set`/`setNullable`. All three
    hosts (Analyze, MyDeals, BoughtDeals) get the feature with no view changes, and the existing autosave picks
    up the applied values.

### Security task (contents of `.claude/security.md`)
Check all new code against security best practices. Make sure there is no sensitive information in the frontend
and no exploitable vulnerability anywhere in the repo. Concretely:
- the API key is backend-only (never a `VITE_` var, wrapped in `Secret`, redacted in logs)
- the route is behind the app-key and session gates and is rate-limited per hour (cost-abuse guard)
- input lengths are bounded
- the note is fenced as data in the prompt
- the model output is schema-validated, URLs are restricted to http(s), and nothing goes through `v-html`
- upstream errors don't leak exception text
- `pip-audit` / `npm audit` stay clean
- run the `security-review` skill on the branch diff

## Todo (≈ 9 h)
- [x] T1 (10 m) Write `tasks/todo/ArvEstimateWithClaude.md` mirroring this plan; commit on the branch.
- [ ] T2 (30 m) Pin `anthropic`; schemas `ArvEstimateReq` / `ArvEstimateRes` / `ArvComparableProperty`.
- [ ] T3 (60 m) Prompt builder with shared + FLIP + BRRRR sections and the fenced note.
- [ ] T4 (75 m) Anthropic client: streaming, web search, structured output, pause_turn loop, refusal/fallback,
      validation + post-checks.
- [ ] T5 (40 m) Router `/arv-estimate`: rate limit, audit, 503/502/429, wiring; env vars + README.
- [ ] T6 (20 m) MCP: `OPEN_WORLD_TOOLS` entry + tests.
- [ ] T7 (30 m) Frontend types + API method.
- [ ] T8 (120 m) `ArvEstimateWithClaudePopup.vue` (form, loading, result tiles and tables, error, Apply).
- [ ] T9 (40 m) Buttons in RefinanceSection and the FLIP section; popup wiring + apply in `DealInputsForm.vue`.
- [ ] T10 (60 m) Tests (below), run lint/typecheck/vitest/pytest/Playwright.
- [ ] T11 (30 m) Security task (above) + `security-review` skill; fix findings.
- [ ] T12 (10 m) Push the branch, open the PR.

## Tests
- **Unit (pytest)**:
  - the prompt contains the address, the strategy-specific rules (FLIP DOM + conservative, BRRRR 3–4 appraisal
    comps) and the fenced note
  - schema bounds (empty address, 2001-char note, confidence 0/11)
  - the client with a fake Anthropic: happy path, `pause_turn` continuation, refusal, invalid JSON → error,
    `javascript:` URL dropped
- **Unit (vitest)**:
  - the popup renders tiles and tables from a fixture
  - Apply emits the BRRRR values (ARV + lowest ARV) and the FLIP values (sale price)
  - the error state shows the detail
  - DealInputsForm shows the button on the Refinance tab (BRRRR) and on the Flip Strategy tab (FLIP), and
    applying updates the deal
- **Integration (pytest + TestClient)**:
  - `/arv-estimate`: 200 with a stubbed client, 503 with no key, 429 over the limit, 422 on a bad body, 401/403
    behind the gates
  - MCP: `arv_estimate` is listed with `openWorldHint=True`, and calling it through MCP returns the structured
    result (stubbed client)
- **E2E (Playwright, `page.route` mock of `/arv-estimate`)**: open the popup from the Analyze page (BRRRR) and
  from a MyDeals FLIP modal, submit, see the comps table, Apply, and the ARV / sale price field shows the target.

## Verification
- `pytest BackEnd/tests -k "arv or mcp"`, then the full suite.
- `npm run lint && npm run typecheck && npm run test` and the new Playwright spec.
- One live manual call with a real `ANTHROPIC_API_KEY` locally, if available, to confirm that the web search and
  the JSON template come back and render.
