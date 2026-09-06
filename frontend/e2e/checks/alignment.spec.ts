import type { Page } from '@playwright/test';
import { expect, test } from '../fixtures';

/**
 * Everything is straight: controls that share a row share a top and a height.
 *
 * The forms lay their inputs out in CSS grids (and the odd flex row), and the
 * mix of primitives inside one row — a PrimeVue `InputNumber` next to a native
 * `<select class="ui-select">`, a `MoneyInput` next to a `NumberInput` — is
 * exactly where a stray padding, border or line-height shows up as one box
 * sitting a couple of pixels lower or taller than its neighbour. That is
 * visible to a person at a glance and invisible to every other check in this
 * suite, so it is measured here directly from `getBoundingClientRect()`.
 *
 * For each screen, every control (see `CONTROL_SELECTOR`) is attributed to its
 * closest ancestor that is a CSS grid or a flex *row* holding at least two
 * controls. Within that container the controls are grouped into visual rows
 * by their top edge (within `ROW_TOLERANCE` px of the row's first control —
 * the same idea as rounding to the nearest 4 px, without a bucket boundary
 * hiding a 3 px offset). A row of two or more controls is a violation when its
 * tops or its heights differ by more than `MAX_DRIFT` px. Single-control rows
 * are skipped, which is what a phone width produces when a grid collapses to
 * one column — the check still runs there, it just has less to say.
 *
 * Under reduced motion the reveals set their final state synchronously, so a
 * short real-time pause after the hook is visible is enough for layout to be
 * final; nothing here waits on animation.
 */

/** Every form control the design system renders, innermost element wins. */
const CONTROL_SELECTOR =
  '[data-part="input"] input, [data-part="input"], input.ui-input, select.ui-select, .ui-input, .ui-select';

/** Tops this close together are the same visual row. */
const ROW_TOLERANCE = 4;

/** Within a row, tops and heights may differ by at most this much. */
const MAX_DRIFT = 1;

/** Real-time pause after a hook is visible, for the reveal to settle. */
const SETTLE_MS = 150;

/** Modals leave through a 200 ms Vue transition on the frozen clock. */
const TRANSITION_MS = 400;

interface ControlRow {
  tops: number[];
  heights: number[];
  ids: string[];
}

interface ControlContainer {
  /** A short description of the grid or flex row, for the failure message. */
  container: string;
  rows: ControlRow[];
}

/**
 * Measure every multi-control row under `rootTestId`.
 *
 * Runs in the page so the grouping sees live computed styles; only numbers
 * and names come back.
 */
async function readControlRows(
  page: Page,
  rootTestId: string,
): Promise<ControlContainer[]> {
  return page.evaluate(
    ({ rootTestId, selector, tolerance }) => {
      const root = document.querySelector<HTMLElement>(`[data-testid="${rootTestId}"]`);
      if (!root) throw new Error(`no [data-testid="${rootTestId}"] on the page`);

      const SKIPPED_INPUT_TYPES = ['checkbox', 'radio', 'range', 'hidden'];

      // Dedupe nested matches: a `[data-part="input"]` wrapper that contains a
      // matched `<input>` is dropped in favour of the input itself.
      const matches = [...root.querySelectorAll<HTMLElement>(selector)];
      const controls = matches
        .filter((el) => !matches.some((other) => other !== el && el.contains(other)))
        .filter((el) => {
          if (el instanceof HTMLInputElement && SKIPPED_INPUT_TYPES.includes(el.type)) {
            return false;
          }
          const style = getComputedStyle(el);
          if (style.display === 'none' || style.visibility === 'hidden') return false;
          const rect = el.getBoundingClientRect();
          return rect.width > 0 && rect.height > 0;
        });

      const isRowContainer = (el: Element): boolean => {
        const style = getComputedStyle(el);
        if (style.display === 'grid' || style.display === 'inline-grid') return true;
        if (style.display === 'flex' || style.display === 'inline-flex') {
          return style.flexDirection === 'row' || style.flexDirection === 'row-reverse';
        }
        return false;
      };

      // How many controls each ancestor holds, so "≥ 2 control descendants"
      // is one lookup rather than a query per ancestor.
      const controlCount = new Map<Element, number>();
      for (const control of controls) {
        let el: Element | null = control.parentElement;
        while (el) {
          controlCount.set(el, (controlCount.get(el) ?? 0) + 1);
          if (el === root) break;
          el = el.parentElement;
        }
      }

      const containerOf = (control: HTMLElement): Element | null => {
        let el: Element | null = control.parentElement;
        while (el) {
          if (isRowContainer(el) && (controlCount.get(el) ?? 0) >= 2) return el;
          if (el === root) break;
          el = el.parentElement;
        }
        return null;
      };

      const idOf = (control: HTMLElement): string => {
        if (control.dataset.testid) return control.dataset.testid;
        const owner = control.closest<HTMLElement>('[data-testid]');
        if (owner && owner !== root && owner.dataset.testid) return owner.dataset.testid;
        const labelled =
          (control.id &&
            root.querySelector(`label[for="${CSS.escape(control.id)}"]`)?.textContent) ||
          control.closest('label')?.textContent;
        const label = labelled?.replace(/\s+/g, ' ').trim();
        if (label) return `label:${label}`;
        const name = control.getAttribute('name');
        return `${control.tagName.toLowerCase()}${name ? `[name=${name}]` : ''}`;
      };

      const describe = (el: Element, index: number): string => {
        const testid = (el as HTMLElement).dataset?.testid;
        const classes = [...el.classList].slice(0, 4).join('.');
        const tag = el.tagName.toLowerCase();
        const where = testid ? `[data-testid="${testid}"]` : classes ? `.${classes}` : '';
        return `${tag}${where}#${index}`;
      };

      // Attribute each control to its container, in document order.
      const grouped = new Map<Element, HTMLElement[]>();
      for (const control of controls) {
        const container = containerOf(control);
        if (!container) continue;
        const list = grouped.get(container) ?? [];
        list.push(control);
        grouped.set(container, list);
      }

      const result: ControlContainer[] = [];
      let index = 0;
      for (const [container, members] of grouped) {
        const measured = members
          .map((control) => {
            const rect = control.getBoundingClientRect();
            return { id: idOf(control), top: rect.top, height: rect.height };
          })
          .sort((a, b) => a.top - b.top);

        // Cluster by top: a control joins the current row while it is within
        // the tolerance of the row's first control.
        const rows: ControlRow[] = [];
        let current: ControlRow | null = null;
        let rowStart = 0;
        for (const box of measured) {
          if (!current || box.top - rowStart > tolerance) {
            current = { tops: [], heights: [], ids: [] };
            rows.push(current);
            rowStart = box.top;
          }
          current.tops.push(Math.round(box.top * 100) / 100);
          current.heights.push(Math.round(box.height * 100) / 100);
          current.ids.push(box.id);
        }

        result.push({
          container: describe(container, index++),
          rows: rows.filter((row) => row.ids.length >= 2),
        });
      }
      return result.filter((entry) => entry.rows.length > 0);
    },
    { rootTestId, selector: CONTROL_SELECTOR, tolerance: ROW_TOLERANCE },
  );
}

interface AlignmentOptions {
  /**
   * When true, at least one multi-control row must exist, so a screen whose
   * grids all happen to collapse cannot pass this check without measuring
   * anything. Off where a single column is the expected layout.
   */
  expectRows: boolean;
}

/** Measure the screen under `rootTestId` and fail on any crooked row. */
async function expectAligned(
  page: Page,
  rootTestId: string,
  { expectRows }: AlignmentOptions,
): Promise<void> {
  await expect(page.getByTestId(rootTestId)).toBeVisible();
  await page.waitForTimeout(SETTLE_MS);

  const containers = await readControlRows(page, rootTestId);
  const rowCount = containers.reduce((sum, entry) => sum + entry.rows.length, 0);
  test.info().annotations.push({
    type: 'alignment',
    description: `${rootTestId}: ${rowCount} multi-control row(s) measured`,
  });

  const violations: string[] = [];
  for (const { container, rows } of containers) {
    for (const row of rows) {
      const topDrift = Math.max(...row.tops) - Math.min(...row.tops);
      const heightDrift = Math.max(...row.heights) - Math.min(...row.heights);
      if (topDrift <= MAX_DRIFT && heightDrift <= MAX_DRIFT) continue;
      const boxes = row.ids
        .map((id, i) => `${id} (top ${row.tops[i]}, height ${row.heights[i]})`)
        .join(', ');
      violations.push(
        `${rootTestId} > ${container}: tops differ by ${topDrift.toFixed(2)}px, ` +
          `heights by ${heightDrift.toFixed(2)}px — ${boxes}`,
      );
    }
  }

  expect(violations, `misaligned control rows:\n${violations.join('\n')}`).toEqual([]);
  if (expectRows) {
    expect(rowCount, `${rootTestId} has no multi-control rows to measure`).toBeGreaterThan(0);
  }
}

/** Below Tailwind's `md` the Analyze form is one column, so rows are singletons. */
function isNarrow(page: Page): boolean {
  return (page.viewportSize()?.width ?? 0) < 768;
}

test.describe('alignment', () => {
  test('the Analyze form, as BRRRR and then as FLIP', async ({ page }) => {
    await page.goto('/analyze');
    await expectAligned(page, 'form.root', { expectRows: !isNarrow(page) });

    await page.getByTestId('analyze.type-flip').click();
    await expect(page.getByTestId('form.field.salePrice')).toBeVisible();
    await expectAligned(page, 'form.root', { expectRows: !isNarrow(page) });
  });

  test('the My Deals deal modal', async ({ page, seed }) => {
    const deal = await seed.seedActiveDeal('BRRRR', { section: 1 });
    await page.goto('/my-deals');
    const card = page.getByTestId(`mydeals.card.${deal.id}`);
    await expect(card).toBeVisible();
    await card.click();
    // The details block keeps two columns at every width.
    await expectAligned(page, 'mydeals.modal', { expectRows: true });
  });

  test('the Bought Deals deal modal', async ({ page, seed }) => {
    const deal = await seed.seedBoughtDeal('BRRRR');
    await page.goto('/bought-deals');
    const card = page.getByTestId(`boughtdeals.card.${deal.id}`);
    await expect(card).toBeVisible();
    await card.click();
    await expectAligned(page, 'boughtdeals.modal', { expectRows: true });
  });

  test('the liquidity transaction form and settings panel', async ({ page, settle }) => {
    await page.goto('/liquidity');
    await expect(page.getByTestId('liquidity.add-flow')).toBeVisible();

    // One-time: the fields stack, so this measures nothing unless a grid
    // sneaks in — still worth running so the day it does, it is straight.
    await page.getByTestId('liquidity.add-flow').click();
    await expectAligned(page, 'txnform.root', { expectRows: false });

    // Recurring: the frequency/interval row is a 3-column grid at every width.
    await page.getByTestId('txnform.mode-recurring').click();
    await expect(page.getByTestId('txnform.frequency')).toBeVisible();
    await expectAligned(page, 'txnform.root', { expectRows: true });

    // Close, and let the leave transition finish so the backdrop is gone
    // before the next click.
    await page.getByTestId('txnform.cancel').click();
    await settle(TRANSITION_MS);
    await expect(page.getByTestId('txnform.root')).toHaveCount(0);

    // Settings: a single column today; measured so a future row is covered.
    await page.getByTestId('liquidity.settings-open').click();
    await expectAligned(page, 'settings.root', { expectRows: false });
  });
});
