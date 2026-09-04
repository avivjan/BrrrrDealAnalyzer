import { expect, test } from '@playwright/test';
import { findRegressions, type RouteBaseline } from './axe';

/**
 * The axe baseline's comparison rule, held to its own contract.
 *
 * This is the piece that decides whether a phase passes or fails its
 * accessibility gate, and it is the piece a restyle is most likely to expose:
 * too strict and every class rename is a false alarm, too loose and a real
 * regression slips through. It needs no browser, so it is checked here against
 * fixed inputs rather than inferred from a live scan.
 */

test.beforeEach(({}, testInfo) => {
  test.skip(
    testInfo.project.name !== 'chromium',
    'a pure comparison needs checking once, not once per engine',
  );
});

const BASELINE: RouteBaseline = {
  region: { impact: 'moderate', count: 8, examples: ['.card-body'] },
  'color-contrast': { impact: 'serious', count: 3, examples: ['.text-slate-500'] },
};

test('a rule the route has never reported is a regression', () => {
  const found: RouteBaseline = {
    ...BASELINE,
    'button-name': { impact: 'critical', count: 1, examples: ['button'] },
  };
  expect(findRegressions(found, BASELINE)).toEqual(['button-name: new rule (1 element(s))']);
});

test('a known rule failing on more elements is a regression', () => {
  const found: RouteBaseline = {
    ...BASELINE,
    region: { impact: 'moderate', count: 9, examples: ['.card-body'] },
  };
  expect(findRegressions(found, BASELINE)).toEqual(['region: 8 -> 9 element(s)']);
});

test('the same counts pass, whatever the selectors turned into', () => {
  // The whole point of the rule-keyed baseline: a restyle rewrites every
  // Tailwind class chain axe reports, and that must not register as anything.
  const found: RouteBaseline = {
    region: { impact: 'moderate', count: 8, examples: ['.totally-different-class'] },
    'color-contrast': { impact: 'serious', count: 3, examples: ['#pv_id_42'] },
  };
  expect(findRegressions(found, BASELINE)).toEqual([]);
});

test('fewer elements failing, or a rule fixed outright, passes', () => {
  const found: RouteBaseline = {
    region: { impact: 'moderate', count: 2, examples: ['.card-body'] },
  };
  expect(findRegressions(found, BASELINE)).toEqual([]);
});
