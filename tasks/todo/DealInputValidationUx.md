# DealInputValidationUx: make every wrong deal input visible (Lowest ARV > ARV and every other silent guard)

Branch: `claude/festive-fermi-bepxsa` (session-designated; wins over CLAUDE.md's `<task_name>` rule, as on the
previous task). Plan file on the branch: `tasks/todo/DealInputValidationUx.md` (mirrors this plan, checkable, with
estimates). Per CLAUDE.md the plan is checked in with the user before any implementation code.

## Context

Typing a **Lowest ARV Possible** above the **ARV** in a deal modal changes nothing except the box itself: the
result tiles keep their old numbers, nothing turns red, and the value is even thrown away on close. Traced:

- The card modals (`frontend/src/views/MyDeals.vue:430-476`, `frontend/src/views/BoughtDeals.vue:318-353`)
  re-analyze and autosave on every change through a deep watch. The backend rejects the payload with HTTP 400
  `"Lowest ARV cannot exceed ARV."` (`BackEnd/BL/analyze/common/validation.py:121-146,161`).
- Both views swallow it (`MyDeals.vue:453-455` logs, `BoughtDeals.vue:330-332` empty catch), so `currentAnalysis`
  keeps the previous tiles; the autosave 400s too and the footer chip only says "Save failed"; `closeModal`
  re-saves, fails again, closes anyway and the edit is lost.
- The only client-side check, `validateDealInputs` (`frontend/src/utils/dealUtils.ts:234-308`), runs on the
  Analyze page's **Analyze & Save** click and lists messages in the rail. No field is ever marked anywhere.
- The in-form figures (`utils/brrrAutoCalc.ts:269-271`: "Refi loan at the lowest ARV", "Cash-Out Routi
  (Lowest ARV)", the Analyze rail's "Routi (low ARV)") DO recompute with the impossible value, so the form
  contradicts the tiles.

**Audit of every other silent guard** (user asked for each to get the same UX):
1. Every rule in `validateDealInputs` (percent 0-100 ranges, non-negative dollar lines, LTV (0,100], days
   until refi > 0, loan term, lowest ARV ≤ 0, flip ranges) — same silence in the modals.
2. `NumberInput.vue:77-78` / `SliderField.vue:95-96` pass `min`/`max` to PrimeVue `InputNumber`, which clamps on
   blur and emits `update:modelValue`; both components listen to `@input` only, so the box can show `100` while
   the model keeps `150` (must be confirmed against `node_modules` after `npm ci`; it isn't installed here).
   PrimeVue also silently refuses the minus key when `min >= 0`.
3. `DaysOrDateField.vue:53` silently ignores a picked refi date earlier than the buy closing date.
4. Four backend BRRRR percent rules (`vacancyPercent`, `maintenancePercent`, `capexPercent`,
   `property_managment_fee_precentages_from_rent`, `validation.py:109-116`) and "Loan term must be at least 1
   year" (`:101`) have no client mirror at all.
5. A cleared LTV is stored as `undefined` (`useDealField.ts:37-39`), dropped from JSON, and rejected as a 422 by
   `active_deal_schemas.py:39` → "Save failed" with no reason.
6. Backend: FLIP saved deals are never validated (`BL/activeDeal/addActiveDeal.py`, `updateActiveDeal.py`,
   `BL/boughtDeal/addBoughtDeal.py`, `updateBoughtDeal.py` skip `validate_flip_inputs`), so an invalid flip row
   persists and every board read re-analyzes it unvalidated.

User decisions (asked and answered): replace the tiles with a notice while invalid; drop the silent clamp and
show the error instead; closing while invalid asks for confirmation and reverts only the bad fields.

## Design

**Two kinds of problem, two treatments.**
- `invalid` = a value that is wrong (out of range, negative, lowest ARV ≤ 0 or > a positive ARV, LTV blank,
  days until refi ≤ 0, loan term ≤ 0, flip holding time ≤ 0). → red border + shake + inline message that only
  clears when fixed; blocks analyze **and** save.
- `missing` = a required field a brand-new deal legitimately starts at 0 (`purchasePrice`, `arv_in_thousands`,
  `rent`; flip `purchasePrice`, `salePrice`). → keeps today's tab dot + Analyze rail list; blocks analyze
  (the backend 400s on them) but not save (the board allows the zeros, `validation.py:149-164`).

### A. Pure validation module (frontend)
- New `frontend/src/config/dealInputPhaseTabs.ts`: move `PhaseTabKey`, `BRRRR_PHASE_TABS`, `FLIP_PHASE_TABS`
  out of `DealInputsForm.vue:153-171` and add `DEAL_INPUT_FIELD_KEYS_BY_PHASE_TAB` (one home tab per field key)
  and `phaseTabForDealInputField(fieldKey, dealType)`.
- New `frontend/src/utils/dealInputValidation.ts`:
  `DealInputFieldError { fieldKey, message, kind: "missing" | "invalid", phaseTabKey, phaseTabLabel }`,
  `validateDealInputFields(deal, dealType)`, `dealInputErrorMessageByFieldKey(deal, dealType)` (invalid only),
  `hasInvalidDealInput(errors)`. Table-driven, same strings and same order as today's `validateDealInputs`, so
  it becomes a one-line wrapper (`.map(e => e.message)`) and `analyze-validation.spec.ts`,
  `AnalyzeDeal.contract.test.ts`, `dealUtils.test.ts` stay green. Deltas: lowest ARV vs ARV only when ARV > 0
  (mirrors backend); `ltv_as_precent == null` → "LTV is required."; "Loan term must be at least 1 year."; the
  four percent rules with the backend wording.

### B. Field primitives
- Prop `errorMessage?: string` on `MoneyInput`, `NumberInput`, `SliderField`; passed through by
  `AutoDefaultMoneyInput`, `PresetSelectInput`, `DaysOrDateField`.
- Rendering (copy `UiField.vue:130`'s convention): input gets `ui-input-invalid` (`main.css:187`),
  `aria-invalid="true"`, `aria-describedby` → `<p role="alert" data-part="error-message" class="mt-1 text-xs
  text-negative">` directly under the box. Under the box, not in the label row: `AutoDefaultMoneyInput.vue:47-61`
  parks its absolute "auto" control there. `e2e/checks/alignment.spec.ts` measures controls only and the field
  root is `flex flex-col`, so a paragraph under the box moves nothing in the row.
- For the PrimeVue-backed inputs the `aria-*` go through `pt` (`pcInputText.root`) — verify the key after
  `npm ci`, fall back to `inputProps` if it differs.
- **Shake**: a `v-shake="errorMessage"` GSAP directive in `motion/directives.ts`, modelled on `vFlash`
  (`:432-456`): on `updated`, when the message appears or changes and `motionEnabled()`, `gsap.fromTo(el, {x:0},
  {keyframes:{x:[-6,6,-4,4,0]}, duration: SHAKE_DURATION=0.4, ease: EASE.exit, overwrite:'auto',
  clearProps:'transform'})`. Restarts cleanly with no re-keying (focus kept), honours reduced motion and the
  in-app motion setting for free, is inside the 1 s budget of `no-live-tweens.spec.ts`. Register in
  `motion/index.ts`, stub in `src/test/setup.ts:131-136`. (`scripts/audit/bindings.mjs:96` lists valueless
  motion directives; that gate is advisory, so a valued `v-shake` prints a finding only — note it in the plan.)
- **Drop the silent clamp**: remove `:min`/`:max` from the two `InputNumber`s and from the `NumberInput`
  props; `SliderField` keeps `min`/`max` only as the thumb fallback (`:44-45`). Remove the `:min="0" :max="100"`
  call sites (`DealInputsForm.vue:341-342,364-365,373-374,382-383`, `RehabSection.vue:88-89`,
  `RefinanceSection.vue:187-188`, `BuySection.vue:145-168`). The inline error now carries the rule.
- `DaysOrDateField.vue:49-55`: keep refusing the emit but set `linkedDatePickProblem` ("Pick a date on/after the
  buy closing date" / "after" for min 1) rendered as the same `<p role="alert">` under the date box; cleared on
  the next accepted change or when `modelValue`/`anchorDate` change.

### C. `DealInputsForm.vue`
- `const dealInputErrorMessageByFieldKey = computed(() => dealInputErrorMessageByFieldKey(props.deal,
  props.dealType))`; new optional prop `fieldErrorMessages` (default `{}`) on the four BRRRR sections, each
  field gets `:error-message="fieldErrorMessages.<key>"`; FLIP inline fields read the computed directly.
  Hosts pass nothing: the form already has `deal` + `dealType`, so `AnalyzeDeal.vue` gets the live red fields
  with no change.
- Tab marker: `phaseTabHasInvalidInput(key)` → a `bg-negative` dot `form.tab.<key>.has-invalid-input` +
  sr-only "has an invalid input", so a wrong field on a hidden tab is never invisible. The two selectors that
  enumerate tabs (`alignment.spec.ts:247`, `DealInputsForm.test.ts:190`) become
  `[data-testid^="form.tab."][role="tab"]`.

### D. Hosts (`MyDeals.vue`, `BoughtDeals.vue`, kept identical)
- `dealInputFieldErrors` / `hasInvalidDealInputs` computeds from the same function; `lastSavedDealSnapshot`
  (JSON clone set in `openDeal` and after each successful `performSave`).
- `analyzeCurrentDeal`: first line of the debounced body `if (dealInputFieldErrors.value.length) return;`
  (checked at fire time, so a fix inside the 500 ms still analyzes). No request leaves while invalid.
- `performSave`: after the `!isDirty` guard, `if (hasInvalidDealInputs.value) { saveStatus.value = 'error';
  return; }` **without** clearing `isDirty`, so the edits stay pending and the watch resumes autosave on the fix.
  One guard covers autosave, close, move-to-bought and duplicate (`MyDeals.vue:254,270`).
- `closeModal`: while invalid → `confirm("These inputs are invalid and were not saved: <messages>. Close anyway?
  They go back to their last saved values; your other changes are saved.")`; Cancel keeps the modal open; OK
  copies each invalid `fieldKey` from `lastSavedDealSnapshot` onto `editingDeal` then saves as today. The app
  already uses `confirm` (`e2e/fixtures/dialogs.ts`).
- Results panel (`MyDeals.vue:997-1075`, `BoughtDeals.vue:1093-1260`): keep the panel and its
  `*.modal.results` hook (`no-live-tweens.spec.ts` waits on it); the tile grid gets
  `v-if="!dealInputFieldErrors.length"`, `v-else` a `<div data-testid="mydeals.modal.results-paused"
  role="status" class="rounded-ctl border-ui border-negative/40 bg-negative/5 p-3 text-sm text-fg">`:
  "Results paused until the highlighted inputs are fixed:" + one line per error "`{message}` — {tab} tab"
  (missing ones under "Still needed:").
- Save chip: `:status="hasInvalidDealInputs ? 'error' : saveStatus"` and a first branch "Not saved — fix the
  highlighted inputs".

### E. `brrrAutoCalc.ts:270`
`lowestArvEffective` = the override only when it is > 0 and ≤ ARV (when ARV is known), else `null`, so the
conservative loan, both wires and the Analyze rail's "Routi (low ARV)" read "—" while the override is unusable.

### F. `AnalyzeDeal.vue` (optional, 5 lines)
A watch that empties `validationErrors` once `validateDealInputs` returns nothing, so the rail list doesn't
outlive the fix now that fields go red live.

### H. Backend
- Close the FLIP gap: in `validation.py` extract `_flip_range_and_sign_errors(payload)` from lines 178-210, add
  `validate_flip_inputs_for_saved_deal(payload)` (those + `holding_time_months <= 0`; allows 0 sale/purchase
  price like the BRRRR twin), call it in the FLIP branches of the four add/update BL functions.
- **MCP support task**: no new tool — `mcp_server.py:592-593` already passes the 400 text through as a
  `RuntimeError`. Add tests in `tests/test_mcp_tools.py`: `analyze_brrr` and `update_deal` with `lowestArv: 999`
  → `pytest.raises(RuntimeError, match="HTTP 400.*Lowest ARV cannot exceed ARV")`; `add_active_deal` FLIP with
  `holdingTime: 0` → `HTTP 400.*Holding time`.
- **Security task** (contents from `.claude/security.md`): check all new code for security best practices, no
  sensitive information in the frontend, no exploitable vulnerabilities. Concretely: every message is a static
  string rendered by Vue's escaping (no `v-html`), the `confirm` text is built from those strings only, no new
  endpoint or secret, the backend change only narrows accepted input; run the `security-review` skill on the
  branch diff.

## Todo (≈ 8 h)
- [x] T1 (10 m) Write `tasks/todo/DealInputValidationUx.md` mirroring this plan; commit on the branch.
- [x] T2 (60 m) A: `config/dealInputPhaseTabs.ts`, `utils/dealInputValidation.ts`, `validateDealInputs` wrapper.
- [x] T3 (30 m) `vShake` directive + registration + test stub.
- [x] T4 (75 m) B: primitives' `errorMessage` anatomy, pass-throughs, `DaysOrDateField` message, drop the
  clamp and its call sites; confirm the PrimeVue blur-clamp finding once `node_modules` exists and record it.
  *Confirmed in `primevue/inputnumber/index.mjs`: `onInputBlur` runs `validateValue` (the min/max clamp), rewrites
  `input.value` to the clamped text and reports it only through `updateModel` → `update:modelValue`, which
  `NumberInput`/`SliderField` never listened to (they emit on `input` only). So a typed 150 showed as 100 while the
  model kept 150. Dropping `min`/`max` removes the rewrite; the inline error carries the rule.*
- [x] T5 (60 m) C: form error map, section prop, tab marker, the two selector fixes.
- [x] T6 (15 m) E: `brrrAutoCalc` guard.
- [x] T7 (90 m) D: both hosts (gating, results notice, chip, `closeModal` confirm + revert).
- [x] T8 (10 m) F: Analyze rail live-clear.
- [x] T9 (40 m) H: FLIP saved-deal validator + call sites; `verify_regression.py`.
- [x] T10 (15 m) MCP support task (tests above).
- [ ] T11 (45 m) E2E specs (below).
- [x] T12 (15 m) Security task. *Result: the `security-review` skill found no HIGH or MEDIUM issue. Every new text sink is a Vue `{{ }}` interpolation (no `v-html` anywhere), the `confirm`/`alert` texts are built from the validator's static strings only, every field whose PrimeVue clamp was dropped is bounded by the backend on both the calculator and the saved-deal paths, and no secret, PII or log line was added.*
- [ ] T13 (20 m) Full gates (`npm test`, `npm run build`, `npm run e2e`, `pytest`); push; open the PR.

## Tests
**Unit (frontend, Vitest)**
- `utils/dealInputValidation.test.ts`: every rule → `fieldKey`/`kind`/tab; wrapper output identical in order to
  the old strings; lowest ARV only checked against a positive ARV; LTV null; loan term; the four percents.
- `motion/directives.test.ts`: `v-shake` tweens `x` with `SHAKE_DURATION` when the message appears/changes;
  quiet when unchanged, empty, or motion is off.
- `MoneyInput.test.ts`, `NumberInput.contract.test.ts`, `SliderField.contract.test.ts`: class, `aria-invalid`,
  `aria-describedby` → the `role="alert"` paragraph; nothing rendered without a message; no clamp on blur.
  `AutoDefaultMoneyInput.test.ts`, `PresetSelectInput.test.ts` pass-through; `DaysOrDateField.test.ts` gains the
  "date before the anchor" message case.
- `DealInputsForm.test.ts`: lowestArv 400 vs ARV 320 → only that stub carries the message and
  `form.tab.refinance.has-invalid-input` exists; a `missing` field has no inline message; FLIP holdingTime 0
  marks `flipStrategy`.
- `brrrAutoCalc.test.ts`: override above ARV → `lowestArvEffective`, `conservativeRefiLoanAmount`,
  `cashOutWireConservative` null.
- New `MyDeals.invalidInput.contract.test.ts` + `BoughtDeals.invalidInput.contract.test.ts` on the settle-test
  harness (`MyDeals.settle.contract.test.ts:66-92`): lowestArv 400 → no `analyzeDeal` / no PUT after 3 s,
  `results-paused` shown, tiles gone, chip error text; fix to 300 → one analyze + one PUT, tiles back; close
  while invalid with `confirm` false → modal stays; true → PUT body carries the saved `lowestArv`;
  move-to-bought / duplicate while invalid do not PUT.
- `AnalyzeDeal.contract.test.ts`: rail list clears once the form validates.

**Integration (backend, pytest)**
- `test_saved_deal_validation.py`: FLIP active/bought twins — blank zeros save; `holdingTime` 0 and
  `capitalGainsTax` 101 → 400 with the calculator's text; a rejected PUT leaves the row unchanged.
- `test_mcp_tools.py`: the three MCP 400 pass-through cases.

**E2E (Playwright)**
- `e2e/flows/my-deals-invalid-input.spec.ts`: seeded BRRRR; `setField('lowestArv', 400)` → the field's
  `[data-part="error-message"]` text, `aria-invalid`, tab marker, `mydeals.modal.results-paused`, chip; `api`
  shows no POST `/analyze/brrr` and no PUT after `settle(2500)`; then 300 → one of each and the conservative
  tile visible; then 400 + close → `expectDialogs([...])`, reopen shows `$300,000`. A bought-deal twin.
- `alignment.spec.ts`: selector fix plus one measurement with a message showing.
- A short `@motion` spec (chromium-motion project): non-identity `transform` on the input right after the
  message appears.
- `hooks-inventory` guarantees every new testid exists.

## Critical files
- `frontend/src/utils/dealUtils.ts` (rules lifted into `utils/dealInputValidation.ts`)
- `frontend/src/components/DealInputsForm.vue`, `components/deal/brrr/*Section.vue`
- `frontend/src/components/ui/MoneyInput.vue`, `NumberInput.vue`, `SliderField.vue`, `AutoDefaultMoneyInput.vue`,
  `PresetSelectInput.vue`, `DaysOrDateField.vue`
- `frontend/src/motion/directives.ts`, `motion/index.ts`, `src/test/setup.ts`
- `frontend/src/views/MyDeals.vue`, `views/BoughtDeals.vue`, `views/AnalyzeDeal.vue`
- `frontend/src/utils/brrrAutoCalc.ts`
- `BackEnd/BL/analyze/common/validation.py` + the four FLIP add/update BL functions; `BackEnd/tests/test_mcp_tools.py`

## Verification
- `cd frontend && npm ci && npm test && npm run build` (vue-tsc type check) and `npm run e2e` (needs the compose
  Postgres / throwaway backend, as the existing suite does).
- `cd BackEnd && pytest` and `python verify_regression.py` (goldens are valid payloads, so they should not move).
- Manual: open a saved BRRRR deal, type a Lowest ARV above the ARV → red shaking box, message, red dot on the
  Refinance tab, "Results paused" notice, chip "Not saved — fix the highlighted inputs", no network request;
  fix it → everything resumes; type 150 in Down Payment → same treatment instead of a silent 100; pick a refi
  date before the buy date → inline message. Through MCP, `analyze_brrr` with `lowestArv: 999` returns the
  400 text.
