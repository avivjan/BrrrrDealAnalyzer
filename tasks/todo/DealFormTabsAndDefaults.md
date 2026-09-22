# DealFormTabsAndDefaults: tabbed deal inputs, "needed" fields, Drive link + PDF on bought deals, budget & broker-fee defaults

Branch `claude/zen-hopper-uo9oai` from `main` (the session's designated branch stands in for a `<task_name>` branch).

## Context

Six owner asks after using the site, all on the deal-input UI shared by Analyze, My Deals and Bought Deals:

1. **Tabs instead of one long scroll.** `DealInputsForm.vue` renders 4 lifecycle sections for BRRRR and 3 for
   FLIP one under the other; too long inside the card modals. Each phase becomes a tab. Results must be visible
   whatever tab is active → the results panel stays *outside* the tabs, directly under them (owner's choice);
   on Analyze the sticky rail already echoes the wires.
2. **Highlight the fields that must be typed to get a first result** (no meaningful default). BRRRR: Purchase
   Price, Actual Rehab Cost, Monthly Rent, Annual Insurance, Annual Taxes, ARV. FLIP: Purchase Price, Rehab
   Cost, Projected Sale Price, Annual Taxes, Annual Insurance (owner's choice). Today a red asterisk marks
   `required`, but it also sits on LTV / long-term rate / days-to-refi, which *have* defaults.
3. **Google Drive link on every bought deal**, a clickable link with a Drive icon on the card. Owner chose a
   **new dedicated field** (`google_drive_link`), not `pics_link`.
4. **PDF report for bought deals.** Only the My Deals modal has "View Report"; `POST /reports/*-pdf` takes the
   full inputs body (no deal id, no `extra=forbid`), so the bought modal reuses it with no backend change.
5. **Construction Loan Budget seeds to actual rehab × (1 + contingency)** (110% at the default 10%), frontend
   only (owner's choice). Today the mirror-once seeds budget = rehab, so the contingency is paid out of pocket.
6. **Broker Processing Fee default 0** (today $395 in the frontend defaults, Pydantic and the DB default).

## Design

### 1. Tabs (`frontend/src/components/DealInputsForm.vue`)
- A `UiTabs` row (`components/ui/UiTabs.vue`) above the sections, one `UiButton variant="tab" :active` per
  phase (`role=tab` / `aria-selected` come from `UiButton.vue:110-111`), `data-testid="form.tab.<key>"`, like the
  deal-type tabs in `views/AnalyzeDeal.vue:156-173`.
  - BRRRR: `buy` Buy · `rehab` Rehab · `rentHolding` Rent & Holding · `refinance` Refinance.
  - FLIP: `buyRehab` Buy & Rehab · `flipStrategy` Flip Strategy · `expenses` Expenses.
- `activePhaseTabKey`: local `ref`, first tab by default, reset when `dealType` changes.
- Sections stay **mounted** and switch with `v-show` (not `v-if`): RehabSection's `mirroredOnce` survives, vitest
  specs that `wrapper.find` fields in any section keep working, Playwright can still resolve hidden fields.
  `v-show` and `data-form-tab="<key>"` go straight on `<BuySection …>` etc. in `DealInputsForm.vue:184-187`
  (single-root components, attrs fall through to the `<section>`), and on the three FLIP `<section>`s inline.
  No change to `LifecycleSection.vue` or the four section components for this item.
- `v-reveal` (`motion/directives.ts:260-278`) only tweens opacity/transform at mount and never touches
  `display`, so a hidden section simply appears without a fade later. Acceptable.
- Each tab shows a small dot (`aria-hidden`) + `sr-only` "needs input", testid `form.tab.<key>.needs-input`, while
  any of its "needed" fields (item 2) is still empty / 0: one `NEEDED_FIELDS_BY_PHASE_TAB` map + one computed
  over `toNumber(props.deal[key])`.
- Results: **no change** in `MyDeals.vue` / `BoughtDeals.vue`; the `Analysis Results` panel already sits after
  `<DealInputsForm>` and is now reachable on every tab.
- E2E (`frontend/e2e`): `fixtures/form.ts` `setField` reads the field's owning tab via
  `fieldRoot(...).locator('xpath=ancestor-or-self::*[@data-form-tab]')` and clicks `form.tab.<key>` unless it is
  `aria-selected="true"`. `flows/analyze-flip.spec.ts:33` and `checks/alignment.spec.ts:248` (both wait for
  `form.field.salePrice` right after switching to FLIP) wait for `form.tab.flipStrategy` instead;
  `alignment.spec.ts` clicks through each `form.tab.*` so it measures every tab. `no-live-tweens.spec.ts:135`
  types into three tabs and is covered by the new `setField`.
- **Pre-existing breakage to fix in the same PR:** `fixtures/payloads.ts` `BRRRR_FORM_FIELDS` still lists
  `closingCostsBuy`, `closingCostsRefi`, `cashReserve`, none rendered by the BRRRR form since the lifecycle
  refactor, so `analyze-brrr.spec.ts` / `axe-modals.spec.ts` fail today. Drop the three; build the saved-body
  expectation in `analyze-brrr.spec.ts:83` from the fields actually typed (as `analyze-flip.spec.ts:72-81` does);
  re-record `analyze-brrr-save` / `analyze-flip-save` goldens and the axe baselines.

### 2. "Needed to run" fields (`components/ui/MoneyInput.vue`)
- New boolean prop `neededToRunAnalysis` (all eleven fields are `MoneyInput`s): label `font-semibold text-primary`
  (`MoneyInput.vue:132-136`), input `border-primary/60` (`ui-input` is `@layer components`, so the utility wins;
  tokens `primary`/`line` in `tailwind.config.js:34,37`). The existing `required` asterisk stays as is (it means
  "must be non-empty"; the emphasis means "type this first"), so LTV / rate / days-to-refi keep their asterisk
  without the emphasis.
- Set on: `BuySection.vue:80-88` purchasePrice; `RehabSection.vue:49-56` rehabCost; `RentHoldingSection.vue`
  rent (:28-35), annual_property_taxes, annual_insurance (:70-83); `RefinanceSection.vue:54-62` arv_in_thousands;
  FLIP in `DealInputsForm.vue` purchasePrice (:211), rehabCost (:224), salePrice (:313), taxes/insurance (:418-431).

### 3. Google Drive link (new shared column)
| Layer | Change |
| --- | --- |
| DAL | `google_drive_link = Column(String, nullable=True)` on the `BaseDeal` mixin (`BackEnd/DAL/data_models/common/base_deal.py:18` neighbour) → `active_deals`, `flip_deals`, `bought_brrrr_deals`, `bought_flip_deals`. |
| Migration | at the end of `_run_migrations_locked` (`BackEnd/migrations/runner.py:152-155`), with a fresh `sa_inspect(engine)`: `add_column_if_missing(engine, inspector, table, "google_drive_link", "VARCHAR", None)` for the four tables. |
| Pydantic | `google_drive_link: Optional[str] = Field(None, max_length=MAX_URL)` in `BackEnd/ReqRes/common/base_deal.py` (next to `pics_link:41`; snake_case, no alias, like the other shared fields). `from_attributes=True` carries it into responses; CRUD iterates `__table__.columns` → no change. `BL/deals/compact.py` rows carry no links today → unchanged. |
| Frontend types | `google_drive_link?: string` on `BaseDealReq` (`frontend/src/types/index.ts:38` neighbour). |
| Modals | "Google Drive Link" input + `Open` anchor (`safeHref`, `target=_blank rel=noopener noreferrer`) under Photos Link in both modals (`MyDeals.vue:932-952`, `BoughtDeals.vue:958-978` pattern); testids `mydeals.modal.google-drive-link` / `boughtdeals.modal.google-drive-link`. |
| Bought card | `components/BoughtDealCard.vue` header block (:219-242): when set, an `<a>` with an inline Google-Drive SVG glyph + "Drive" text beside the address, `@click.stop`, `:href="safeHref(...)"`, `target=_blank rel=noopener noreferrer`, `aria-label`, `data-testid="boughtcard.google-drive-link"`. `DealCard.vue` (My Deals board) untouched: the ask is bought deals only. |
| Copy-for-AI | one `Google Drive:` line after `utils/dealUtils.ts:434`. |
| MCP | no new tool; the field reaches every deal tool through OpenAPI; tools/list budget (300 kB vs ~256 kB) is fine; re-snapshot goldens (`endpoints.json` gains `"google_drive_link": null`, `models.json` schema). |

### 4. PDF for bought deals
- Extract from `MyDeals.vue:474-542` into `frontend/src/composables/useDealReportPdf.ts` (`isPreparingPdf`,
  `pdfPreview`, `viewDealReport(deal, dealType)`, `downloadFromPreview`, `closePdfPreview`, revoke on unmount) and
  the overlay `MyDeals.vue:1391-1456` into `components/deal/DealReportPdfPreviewModal.vue` (props `preview`,
  `testIdPrefix`; emits `download`, `close`; keeps `UiTransition preset="modalEnterOnly"`). The contract tests
  `vi.mock("../api")` by module path, which the composable's import resolves to as well.
- `MyDeals.vue` keeps prefix `mydeals` → `e2e/flows/pdf-report.spec.ts` testids unchanged.
- `BoughtDeals.vue`: "View Report" button in the modal header actions (:732-753, before the copy icon,
  `data-testid="boughtdeals.modal.view-report"`), prefix `boughtdeals`, endpoint from `editingDealType`.
  Payload = the bought deal serialised whole (extra fields are ignored by `analyzeBRRRReq` / `analyzeFlipReq`,
  exactly as result fields already are for active deals). `api.downloadDealPdf` unchanged.
- Backend: none. MCP: `DESCRIPTIONS` for `report_brrr_pdf` / `report_flip_pdf` (`mcp_server.py:100-107`) gain
  "works for a bought deal too: pass its body from get_deal / get_bought_deals".

### 5. Construction Loan Budget seed (`components/deal/brrr/RehabSection.vue:25-39`)
- Rehab typed first (both empty): `constructionLoanBudget = round4(rehabCost × (1 + (contingency ?? 0) / 100))`
  (thousands at `Numeric(14,4)`; `50 × 1.1` is `55.000000000000007` in floating point). Same formula as the
  backend backfill (`brrr_lifecycle_columns.py:47-48`) and `brrrAutoCalc.ts:196`.
- Budget typed first: keep copying the budget to rehab unchanged.
- The note lives in the section docblock and a `placeholder` on the budget field; `impactText` is generated
  ("Affects: …") and is not the place.
- Tests: `DealInputsForm.test.ts:399-410` (40 → 44 at the default 10%), plus a contingency-0 case; `:412-418`
  (saved deal never mirrors) unchanged.

### 6. Broker Processing Fee default 0
- Frontend `BRRR_LIFECYCLE_DEFAULTS.brokerProcessingFeeRefi: 0` (`utils/dealUtils.ts:131`).
- Backend `broker_processing_fee_refi` default `Decimal("0")` + description "($0 by default; $395 when the broker
  charges one)" in `ReqRes/common/brrr_lifecycle_inputs.py:96-97` — that description is what MCP shows; DAL
  `server_default='0', default=0` (`DAL/data_models/common/brrr_lifecycle.py:49`); migration row →
  `("broker_processing_fee_refi", "NUMERIC(12,2) DEFAULT 0", "0")` (the file's rule: DDL = model = Pydantic; the
  backfill only runs on a DB that lacks the column) and an unconditional idempotent
  `ALTER TABLE … ALTER COLUMN broker_processing_fee_refi SET DEFAULT 0` for both BRRRR tables next to
  `brrr_lifecycle_columns.py:81-85`. Existing rows keep their stored value.
- `RefinanceSection.vue:198`: quick button becomes `$395` (sets 395); testid `form.processing-zero` →
  `form.processing-395` (no other references).
- `tests/test_migrations.py:85` → `Decimal("0")`; re-snapshot goldens.

## Todo (≈ 5 h 30)
- [x] T1 (10 min) Plan file `tasks/todo/DealFormTabsAndDefaults.md` on the branch; commit.
- [x] T2 (30 min) Backend: broker fee default/description/DAL/migration row + `SET DEFAULT 0`; Drive column on
      the mixin, Pydantic field, four-table migration loop.
- [x] T3 (25 min) Backend tests — **Integration** (`test_migrations.py`: backfill 0, `SET DEFAULT` after two runs,
      `google_drive_link` present + NULL on all four tables; `test_deal_crud.py`: Drive link round-trips
      create/update/move-to-bought for BRRRR and FLIP, 2,000-char cap, omitted broker fee → 0), **Unit**
      (`test_brrr_lifecycle.py`: refi total with the fee omitted excludes 395); `pytest`;
      `python3 verify_regression.py snapshot` then `verify`.
- [x] T4 (30 min) Frontend data: `dealUtils.ts` default + clipboard line, `types/index.ts`, Drive inputs in both
      modals, `BoughtDealCard.vue` icon link, `$395` button.
- [x] T5 (20 min) Budget seed in `RehabSection.vue` (+ docblock/placeholder).
- [x] T6 (25 min) `MoneyInput.vue` `neededToRunAnalysis` + the 11 call sites.
- [x] T7 (45 min) Tabs in `DealInputsForm.vue`: tab row, `v-show` + `data-form-tab`, reset on type change,
      needs-input dot.
- [x] T8 (40 min) PDF: `useDealReportPdf.ts`, `DealReportPdfPreviewModal.vue`, rewire My Deals (same testids),
      Bought "View Report".
- [x] T9 (50 min) Frontend tests — **Unit**: `DealInputsForm.test.ts` (tabs render per type, first tab active,
      switching toggles `v-show`, reset on type change, hidden fields still round-trip, dot follows needed fields,
      mirror-seed 40 → 44 and contingency 0, `createEmptyDealForm().brokerProcessingFeeRefi === 0`);
      `MoneyInput.test.ts` (emphasis classes on label/input); `BoughtDealCard.contract.test.ts` (Drive anchor
      href/rel, absent when unset, click does not open the card); `dealUtils` clipboard line; new
      `useDealReportPdf.test.ts` (blob URL create/revoke, filename); `BoughtDeals.*.contract.test.ts` (View
      Report calls `api.downloadDealPdf` with the bought deal and opens `boughtdeals.pdf-modal`).
      `npm test`, `npm run build`.
- [x] T10 (35 min) **E2E**: `fixtures/form.ts` tab-aware `setField`; `payloads.ts` drop the three unrendered
      BRRRR fields; `analyze-brrr.spec.ts` expectation from typed fields; `analyze-flip.spec.ts:33` +
      `alignment.spec.ts:248` wait on the Flip Strategy tab and walk every tab; `pdf-report.spec.ts` bought-deal
      case; `npm run e2e:record` (chromium) then `npm run e2e`.
- [x] T11 (10 min) MCP: no new endpoint; PDF tool descriptions mention bought deals; broker-fee description via
      Pydantic; `tests/test_mcp.py` (descriptions present, tools/list budget) green; goldens re-snapshotted in T3.
- [x] T12 (15 min) Security (`.claude/security.md`): re-read every file touched — the Drive link is user text
      bounded at `MAX_URL`, rendered only through interpolation and bound to `:href` through `safeHref` (no
      `javascript:` / `data:`), `rel="noopener noreferrer"` on every new anchor; the Drive SVG is inline static
      markup (no external fetch); the bought PDF payload is the same body My Deals already sends, still behind
      `require_session`; no secrets in the frontend, no new sinks, no `v-html`; `SET DEFAULT` migration is
      parameter-free DDL on fixed table names.
- [x] T13 (15 min) Final run: `pytest`, `verify_regression.py verify`, `npm test`, `npm run build`, `npm run e2e`;
      push; open the PR.

## Verification
- Setup in this sandbox: `pip install -r BackEnd/requirements.txt`; `cd frontend && npm ci`. Docker is not
  available, but Postgres 16 is installed locally (cluster `16/main`, down): `pg_ctlcluster 16 main start`,
  create role/db `brrrr_test`/`brrrr_test`, then run pytest in `BackEnd/` with
  `TEST_DATABASE_URL=postgresql+psycopg2://brrrr_test:brrrr_test@127.0.0.1:5432/brrrr_test` (conftest requires a
  loopback host and a `_test` database name). Chromium is pre-installed for Playwright (`/opt/pw-browsers`);
  webkit projects may be skipped if not installed.
- Backend: `pytest`; `python3 verify_regression.py verify`.
- Frontend: `npm test`; `npm run build`; `npm run e2e` (record first where goldens change).
- Manual: `npm run dev` + backend. Analyze: switch tabs, the rail keeps updating, the dot clears as needed fields
  are typed; type 50 into Actual Rehab → budget 55. My Deals card: results sit under the tabs on every tab.
  Bought deal: set a Drive link, the card shows the Drive icon link and clicking it does not open the modal;
  "View Report" opens the PDF preview and Download offers `BigWhales_<type>_<address>.pdf`.
- MCP: `analyze_brrr` with `brokerProcessingFeeRefi` omitted → refi closing total excludes 395; `report_brrr_pdf`
  with a body from `get_bought_deals` returns the PDF blob; `get_deal` shows `google_drive_link`.

## Review
The shared deal form is four (BRRRR) or three (FLIP) phase tabs with every section kept mounted behind
`v-show`; the results panel sits under the tabs in both modals and the Analyze rail is unchanged. The six
BRRRR and five FLIP inputs the analysis cannot run without carry `neededToRunAnalysis` (bold primary label,
primary border) and a tab dots itself while one of its needed inputs is still 0. `google_drive_link` is a
nullable column on all four deal tables (idempotent migration, both boots verified), a Pydantic field capped
at `MAX_URL`, an input in both modals and a Drive-icon link on the bought card through `safeHref`. The bought
modal offers "View Report" through the `useDealReportPdf` composable and the `DealReportPdfPreviewModal`
lifted out of My Deals (same test ids). Typing the actual rehab first seeds the budget at rehab × (1 +
contingency), rounded to 4 decimals in thousands; the broker processing fee defaults to $0 (form, Pydantic,
DB default via `SET DEFAULT 0`, stored rows untouched) with a `$395` quick button.

E2E drift found and fixed along the way (the suite had not been run since the lifecycle refactor):
`BRRRR_FORM_FIELDS` listed three lump-sum fields the form no longer renders; the form fixture matched the
linked date input of an anchored `DaysOrDateField`; the modal-scroll footer locator also matched section
footers; the analyze-brrr spec read a removed "with buffer" tile; a native date box was 2px taller than the
number box beside it (now pinned in `main.css`). Goldens re-recorded on chromium, which also catches them up
with the lifecycle and breakdown fields main already returns.

Backend: pytest green on Postgres 16 (whole suite), `verify_regression.py verify` identical after
re-snapshot, bandit clean, the CI migration smoke (two boots on a fresh database) passes. Frontend:
1516 vitest tests pass, `vue-tsc -b && vite build` clean, Playwright chromium 109 passed / 3 skipped
(webkit projects not run here: the sandbox has no WebKit build).
