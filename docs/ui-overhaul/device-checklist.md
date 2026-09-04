# Real-device checklist — UI overhaul

Emulation is not a device. Playwright's `iPhone 14` project gets the viewport and
the coarse pointer right and gets everything below wrong: it has no software
keyboard, no browser chrome that grows and shrinks as you scroll, no `100vh`
lie, no OS-level Reduce Motion switch, and no notch. Every one of the Phase 0
baseline defects at the bottom of this page is invisible to it.

So this pass is manual, and it is run **once per phase**, on real hardware,
before that phase is called done.

## How to run it

Serve the app on the LAN (`npm run dev -- --host`) with the backend reachable
from the phone, or point the phone at a deployed preview. Work through every box
in order. A box is ticked only if the behaviour is right *and* nothing else
regressed while you were looking at it.

Record the date, the phase, the iOS version and the device in the log at the
bottom.

## iPhone — Safari

- [ ] All six routes open and render: `/`, `/analyze`, `/my-deals`,
      `/bought-deals`, `/liquidity`, `/reps`
- [ ] Landing: every feature card is reachable and tappable without horizontal
      scrolling
- [ ] Open a deal card → the modal opens and covers the whole screen, with no
      strip of board visible at any edge
- [ ] Edit a money field in that modal → the keyboard opens, the value commits
      on dismiss, and the autosave chip goes **Saving… → Saved → (clears)**
- [ ] Close the modal → you are back on the board at the same scroll position
- [ ] Bought Deals: toggle a substage checkbox → the chip saves, and the tick
      survives a pull-to-refresh
- [ ] Liquidity: **Add Flow** → the form opens, the date field uses the native
      picker, saving shows a toast
- [ ] Liquidity: the chart is reachable and a day can be selected
- [ ] REPS: start the stopwatch, background the app for 30 s, return → the
      elapsed time is still correct
- [ ] REPS: stop, then **Discard** → the confirm names what will be lost
- [ ] Rotate to landscape on every route → nothing is clipped, nothing sits
      under the notch, and the safe-area insets are respected
- [ ] Rotate back to portrait → no layout is left stretched or scrolled sideways
- [ ] Settings → Accessibility → Motion → **Reduce Motion ON**, then reload:
      every route's content is **immediately visible**, never faded-in-from-zero
      and never left invisible
- [ ] Tap any text or number input → **the page does not zoom**
- [ ] Scroll a board to its bottom → the last row is fully readable above the
      Safari toolbar

## iPhone — Chrome

Chrome on iOS is WebKit with a different chrome; the toolbar behaviour and the
viewport arithmetic differ from Safari's, which is exactly where clipping hides.

- [ ] All six routes open and render
- [ ] Open a deal modal, edit a money field, watch the autosave chip
- [ ] Toggle a Bought Deals substage
- [ ] Liquidity add-flow
- [ ] REPS timer start / stop
- [ ] Rotate to landscape → nothing clipped, safe areas respected
- [ ] Reduce Motion ON → content immediately visible
- [ ] Tap an input → the page does not zoom
- [ ] Scroll a board to its bottom → the last row clears the toolbar

## Desktop — Chrome

- [ ] Every flow the automated suite covers, done by hand once: analyze and save
      a deal, autosave an edit, duplicate, delete, move to Bought, edit the
      pipeline template, generate a PDF report, send an offer, add a liquidity
      flow, log a REPS entry
- [ ] **Keyboard only** (no mouse at all): Tab reaches every control on every
      route in a sensible order
- [ ] Keyboard only: the focus ring is visible on every control it lands on
- [ ] Keyboard only: a deal modal can be opened, edited and closed
- [ ] Keyboard only: the liquidity chart can be focused and walked with the
      arrow keys, and the day panel updates
- [ ] Keyboard only: no focus trap — nothing swallows Tab or Escape

## Phase 0 baseline observations

These are **known defects as of the `ui-baseline` tag**. They are recorded, not
fixed, in Phase 0. Tick a box the first time you confirm the behaviour on real
hardware; note the phase that fixes it beside the box.

- [ ] **Input zoom on focus.** Tapping an input under 16 px zooms the page on
      iOS Safari and does not zoom back out. Fixed in phase: ______
- [ ] **Board bottom clipped under the iOS toolbar.** The last kanban row on
      `/my-deals` and `/bought-deals` sits behind Safari's bottom bar and cannot
      be scrolled clear. Fixed in phase: ______
- [ ] **Card actions unreachable on touch.** Delete / duplicate / move-to-bought
      on a deal card only appear on `:hover`, so on a touch device they are
      invisible until a tap has already opened the modal. Fixed in phase: ______
- [ ] **Liquidity header wider than any phone.** `/liquidity` lays Back, Today,
      Mercury, Settings and Add Flow out in one unwrapped row. On iPhone the row
      runs off the right edge; on a Pixel the browser zooms the whole page out
      to about 494 CSS px to fit it, shrinking every label. Fixed in phase: ____
- [ ] **Liquidity sidebar missing on phones.** The balance breakdown and the
      recurring-series list live in an `lg:`-only sidebar, so on a phone there
      is no way to see per-account balances or to edit or delete a recurring
      series at all. Fixed in phase: ______

The last two are also asserted by the e2e suite: `e2e/flows/liquidity.spec.ts`
records the header's width requirement and skips the sidebar-driven flows on
narrow viewports, and both will fail — deliberately — once the layout is fixed.

Anything new found during a pass gets appended here with the date, so the next
phase inherits the list rather than rediscovering it.

## Log

| Date | Phase | Device | OS | Browser | Result | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| | 0 | | | | | baseline pass not yet run |
