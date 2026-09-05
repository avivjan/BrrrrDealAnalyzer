import { expect, test, type Page } from '../fixtures';

/**
 * The deal modals stay scrollable, on every device size.
 *
 * This exists because of a real defect. `UiModalPanel` gives a modal exactly
 * one scroller — `[data-part="body"]`, which is `flex-1 min-h-0 overflow-y-auto
 * overscroll-contain` inside a panel capped at `max-h-[90svh]`. Both deal views
 * then wrapped their body content in a second `overflow-y-auto
 * overscroll-contain` div. That div has no height cap, so it always grows to
 * its content and can never scroll — but it is still a scroll port, and
 * `overscroll-contain` stops a scroll that reaches its boundary from chaining
 * to an ancestor. A wheel over the modal therefore landed on an element that
 * could not move and was forbidden from passing the gesture on, so the modal
 * did not scroll at all with a mouse. Touch was unaffected: it scrolls the
 * nearest ancestor that can actually move, so phones behaved correctly and the
 * bug looked desktop-only.
 *
 * Nothing in the existing suite could catch that. `scrollTop = n` from script
 * drives the target element directly and bypasses chaining entirely, so the
 * body always looked healthy; only a real gesture, or an inspection of the
 * chain between the body and its content, sees the trap. Both are asserted
 * here, on all four device projects, because the failure is a function of the
 * input device rather than of the code path.
 */

interface PanelMetrics {
  /** The panel's own box, to check it fits on screen. */
  panel: { top: number; bottom: number; height: number };
  viewportHeight: number;
  /** The body is the scroller: it must have more content than room. */
  body: { clientHeight: number; scrollHeight: number; scrollTop: number };
  /**
   * Descendants of the body that are scroll ports which cannot scroll *and*
   * refuse to chain. Each one silently swallows a wheel. Native form controls
   * are excluded: a `<textarea>` is a scroll port by default but leaves
   * `overscroll-behavior` at `auto`, so a gesture it cannot use passes through.
   */
  traps: string[];
}

async function readPanel(page: Page): Promise<PanelMetrics> {
  return page.evaluate(() => {
    const panel = document.querySelector('[data-ui="modal-panel"]');
    if (!panel) throw new Error('no [data-ui="modal-panel"] on the page');

    // `:scope >` matters: `UiCard` also marks its content `data-part="body"`,
    // so an unscoped query finds a card deep inside the modal instead.
    const body = panel.querySelector(':scope > [data-part="body"]') as HTMLElement | null;
    if (!body) throw new Error('the panel has no body region');

    const traps = [...body.querySelectorAll<HTMLElement>('*')]
      .filter((el) => {
        const style = getComputedStyle(el);
        const scrollPort = style.overflowY === 'auto' || style.overflowY === 'scroll';
        const stuck = el.scrollHeight <= el.clientHeight;
        const blocksChaining = style.overscrollBehaviorY === 'contain';
        const formControl = ['TEXTAREA', 'SELECT', 'INPUT'].includes(el.tagName);
        return scrollPort && stuck && blocksChaining && !formControl;
      })
      .map((el) => `${el.tagName.toLowerCase()}.${el.className}`.slice(0, 120));

    const rect = panel.getBoundingClientRect();
    return {
      panel: {
        top: Math.round(rect.top),
        bottom: Math.round(rect.bottom),
        height: Math.round(rect.height),
      },
      viewportHeight: window.innerHeight,
      body: {
        clientHeight: body.clientHeight,
        scrollHeight: body.scrollHeight,
        scrollTop: Math.round(body.scrollTop),
      },
      traps,
    };
  });
}

/** Scroll the body the way the app does, then report where it ended up. */
async function scrollBodyBy(page: Page, delta: number): Promise<number> {
  return page.evaluate((by) => {
    const panel = document.querySelector('[data-ui="modal-panel"]')!;
    const body = panel.querySelector(':scope > [data-part="body"]') as HTMLElement;
    body.scrollTop = by;
    return Math.round(body.scrollTop);
  }, delta);
}

const MODALS = [
  {
    name: 'the My Deals detail modal',
    route: '/my-deals',
    open: async (page: Page, seed: { seedActiveDeal: Function }) => {
      const deal = await seed.seedActiveDeal('BRRRR', { section: 1 });
      await page.goto('/my-deals');
      await page.getByTestId(`mydeals.card.${deal.id}`).click();
      await expect(page.getByTestId('mydeals.modal')).toBeVisible();
    },
  },
  {
    name: 'the Bought Deals detail modal',
    route: '/bought-deals',
    open: async (page: Page, seed: { seedBoughtDeal: Function }) => {
      const deal = await seed.seedBoughtDeal('BRRRR');
      await page.goto('/bought-deals');
      await page.getByTestId(`boughtdeals.card.${deal.id}`).click();
      await expect(page.getByTestId('boughtdeals.modal')).toBeVisible();
    },
  },
] as const;

for (const modal of MODALS) {
  test.describe(modal.name, () => {
    test('fits the viewport and scrolls its body', async ({ page, seed }) => {
      await modal.open(page, seed as never);

      const metrics = await readPanel(page);

      // Layout: the panel is capped below the viewport, so its header and
      // footer are both reachable rather than hanging off the screen.
      expect(metrics.panel.top).toBeGreaterThanOrEqual(0);
      expect(metrics.panel.bottom).toBeLessThanOrEqual(metrics.viewportHeight + 1);
      expect(metrics.panel.height).toBeGreaterThan(0);

      // Scrollability: on every one of these viewports this modal's content is
      // taller than the room it has, so the body must be an overflowing
      // scroller. If this ever stops being true the gesture assertions below
      // would pass vacuously, so it is asserted first.
      expect(metrics.body.scrollHeight).toBeGreaterThan(metrics.body.clientHeight);

      const landed = await scrollBodyBy(page, 300);
      expect(landed).toBeGreaterThan(0);
    });

    test('has no scroll trap between the body and its content', async ({ page, seed }) => {
      await modal.open(page, seed as never);

      // The regression itself. A descendant that is a scroll port, has nothing
      // to scroll, and sets `overscroll-behavior: contain` eats any gesture
      // that starts over it.
      const { traps } = await readPanel(page);
      expect(traps, `scroll traps inside the modal body: ${traps.join(', ')}`).toEqual([]);
    });

    test('a wheel over the content scrolls the modal', async ({ page, seed, browserName }) => {
      // `mouse.wheel` is a Chromium capability; the trap it proves is engine
      // independent and the previous test covers it structurally everywhere.
      test.skip(browserName !== 'chromium', 'wheel emulation is Chromium-only');

      await modal.open(page, seed as never);

      const body = page.locator('[data-ui="modal-panel"] [data-part="body"]').first();
      const box = (await body.boundingBox())!;
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.wheel(0, 600);

      await expect
        .poll(async () => (await readPanel(page)).body.scrollTop, {
          message: 'the wheel did not move the modal body',
        })
        .toBeGreaterThan(0);
    });

    test('the footer stays put while the body scrolls', async ({ page, seed }) => {
      await modal.open(page, seed as never);

      const footer = page.locator('[data-ui="modal-panel"] [data-part="footer"]');
      await expect(footer).toBeVisible();
      const before = (await footer.boundingBox())!;

      await scrollBodyBy(page, 100_000); // past the end, to the bottom
      await expect(footer).toBeVisible();
      const after = (await footer.boundingBox())!;

      // The footer is `shrink-0` outside the scroller, so scrolling the body
      // must not move it.
      expect(Math.round(after.y)).toBe(Math.round(before.y));
    });
  });
}
