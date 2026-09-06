import { expect, test } from '../fixtures';
import type { Locator, Page } from '@playwright/test';

/**
 * Kanban drag-and-drop, on chromium only.
 *
 * SortableJS drives these boards through raw pointer events, and synthesising
 * those faithfully is a per-engine art; characterizing the *rules* is what
 * matters here, and the rules are engine-independent. WebKit and the two
 * mobile projects skip this file — mobile renders the plain grid anyway (see
 * `my-deals-autosave`), which is precisely the fallback these drags do not
 * exist in.
 *
 * The four rules being frozen:
 *  - a bought deal may only move one pipeline stage at a time;
 *  - it may only move forward once its substages are ticked;
 *  - a My Deals card dragged one row on writes exactly once;
 *  - reordering inside a column is not a change and must not write.
 */

// Tall enough that all seven pipeline rows fit without scrolling: a drag whose
// drop point is below the fold aims at coordinates the browser never delivers,
// and scrolling mid-drag puts the grab point under the sticky header.
test.use({ viewport: { width: 1280, height: 1600 } });

test.beforeEach(({}, testInfo) => {
  test.skip(
    testInfo.project.name !== 'chromium',
    'drag characterization is recorded and replayed on chromium only',
  );
});

/**
 * SortableJS schedules parts of a drag on `setTimeout`, and this suite runs
 * with a frozen clock — so the drag specs hand the clock back before touching
 * the mouse. They assert stage *rules*, never debounce timing, so nothing is
 * lost by letting real time flow here.
 */
async function withRealTime(page: Page): Promise<void> {
  await page.clock.resume();
}

/**
 * The centre of a box, clamped to what is actually on screen.
 *
 * A drag whose end point is outside the viewport aims the mouse at coordinates
 * the browser never delivers an event to, and the drag silently does nothing.
 * The tall viewport above keeps every pipeline row visible, and this keeps
 * that true for a board that grows another row.
 */
function visibleCentre(
  box: { x: number; y: number; width: number; height: number } | null,
  viewport: { width: number; height: number },
): { x: number; y: number } | null {
  if (!box) return null;
  const left = Math.max(box.x, 2);
  const right = Math.min(box.x + box.width, viewport.width - 2);
  const top = Math.max(box.y, 2);
  const bottom = Math.min(box.y + box.height, viewport.height - 2);
  if (right <= left || bottom <= top) return null;
  return { x: (left + right) / 2, y: (top + bottom) / 2 };
}

/**
 * Where a person grabs a card: its header strip, not its middle.
 *
 * A bought-deal card carries its substage checkboxes down the middle, and a
 * `mousedown` that lands on a checkbox is claimed by the input rather than by
 * SortableJS — the drag silently never starts. Grabbing near the top is both
 * what a user does and the only thing that works.
 */
function grabPoint(
  box: { x: number; y: number; width: number; height: number } | null,
  viewport: { width: number; height: number },
): { x: number; y: number } | null {
  const centre = visibleCentre(box, viewport);
  if (!centre || !box) return null;
  const top = Math.max(box.y, 2);
  return { x: centre.x, y: Math.min(top + 20, centre.y) };
}

/** `mouse.down` → two moves → `mouse.up`, which is what SortableJS listens for. */
async function dragOnto(page: Page, source: Locator, target: Locator): Promise<void> {
  await target.scrollIntoViewIfNeeded();
  const viewport = page.viewportSize()!;
  const start = grabPoint(await source.boundingBox(), viewport);
  const end = visibleCentre(await target.boundingBox(), viewport);
  expect(start, 'drag source is on screen').not.toBeNull();
  expect(end, 'drop target is on screen').not.toBeNull();

  await page.mouse.move(start!.x, start!.y);
  await page.mouse.down();
  // A short nudge first: Sortable only begins a drag once the pointer moves.
  await page.mouse.move(start!.x + 8, start!.y + 8);
  await page.waitForTimeout(60);
  await page.mouse.move((start!.x + end!.x) / 2, (start!.y + end!.y) / 2, { steps: 12 });
  await page.waitForTimeout(120);
  await page.mouse.move(end!.x, end!.y, { steps: 12 });
  await page.waitForTimeout(120);
  await page.mouse.up();
  await page.waitForTimeout(300);
}

test('a bought deal cannot jump two pipeline stages', async ({
  page,
  api,
  dialogs,
  seed,
}) => {
  const deal = await seed.seedBoughtDeal('BRRRR');

  await page.goto('/bought-deals');
  await expect(page.getByTestId(`boughtdeals.card.${deal.id}`)).toBeVisible();
  await withRealTime(page);

  api.reset();

  await dragOnto(
    page,
    page.getByTestId(`boughtdeals.card.${deal.id}`),
    page.getByTestId('boughtdeals.draggable.closed'),
  );

  await dialogs.expectDialogs(['You can only move deals one stage at a time.']);
  expect(api.matching((request) => request.method === 'PUT')).toEqual([]);

  // The *server* still has it on `purchase`. The board's own DOM does not
  // necessarily agree: SortableJS moved the node itself, and `refreshColumns()`
  // re-renders the same `:key` without moving it back — a real baseline defect,
  // written down here rather than asserted away.
  const [stored] = await seed.listBoughtDeals();
  expect(stored!.boughtStage).toBe('purchase');
});

test('a bought deal cannot advance with substages outstanding', async ({
  page,
  api,
  dialogs,
  seed,
}) => {
  const deal = await seed.seedBoughtDeal('BRRRR');

  await page.goto('/bought-deals');
  await expect(page.getByTestId(`boughtdeals.card.${deal.id}`)).toBeVisible();
  await withRealTime(page);

  api.reset();

  await dragOnto(
    page,
    page.getByTestId(`boughtdeals.card.${deal.id}`),
    page.getByTestId('boughtdeals.draggable.prepare_for_closing'),
  );

  expect(dialogs.messages).toHaveLength(1);
  expect(dialogs.messages[0]).toContain(
    'Cannot advance: complete these sub-stages first:',
  );
  expect(api.matching((request) => request.method === 'PUT')).toEqual([]);

  const [stored] = await seed.listBoughtDeals();
  expect(stored!.boughtStage).toBe('purchase');
});

test('dragging a My Deals card to the next stage writes exactly once', async ({
  page,
  api,
  seed,
}) => {
  const deal = await seed.seedActiveDeal('BRRRR', { section: 1, stage: 1 });

  await page.goto('/my-deals');
  await expect(page.getByTestId(`mydeals.card.${deal.id}`)).toBeVisible();
  await withRealTime(page);

  api.reset();

  await dragOnto(
    page,
    page.getByTestId(`mydeals.card.${deal.id}`),
    page.getByTestId('mydeals.draggable.2'),
  );

  await expect
    .poll(() => api.matching((request) => request.method === 'PUT').length)
    .toBe(1);
  await expect(page.getByTestId('mydeals.stage.2')).toContainText(deal.address);

  await api.expectContract('my-deals-drag-stage');
});

test('reordering inside a column writes nothing', async ({
  page,
  api,
  seed,
}) => {
  const first = await seed.seedActiveDeal('BRRRR', {
    section: 1,
    stage: 1,
    address: 'A First St',
  });
  const second = await seed.seedActiveDeal('BRRRR', {
    section: 1,
    stage: 1,
    address: 'B Second Ave',
  });

  await page.goto('/my-deals');
  await expect(page.getByTestId(`mydeals.card.${first.id}`)).toBeVisible();
  await expect(page.getByTestId(`mydeals.card.${second.id}`)).toBeVisible();
  await withRealTime(page);

  api.reset();

  await dragOnto(
    page,
    page.getByTestId(`mydeals.card.${second.id}`),
    page.getByTestId(`mydeals.card.${first.id}`),
  );

  await api.expectNoRequests('a same-column reorder is not a stage change');
});
