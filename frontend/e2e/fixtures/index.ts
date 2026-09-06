import { test as base, expect } from '@playwright/test';
import { API_ORIGIN } from './env';
import { installClock, settle as settleClock } from './clock';
import { DialogRecorder } from './dialogs';
import { NetworkRecorder } from './recorder';
import { Seeder } from './seed';

/**
 * The one `test` every spec imports.
 *
 * Each concern lives in its own file; this composes them into a single fixture
 * set so a spec reads as behaviour, not as setup. Everything is per-test: a
 * fresh recorder, a fresh dialog log, a frozen clock, and a database swept
 * clean afterwards.
 */

export interface Fixtures {
  api: NetworkRecorder;
  dialogs: DialogRecorder;
  seed: Seeder;
  settle: (ms: number) => Promise<void>;
}

export const test = base.extend<Fixtures>({
  // All three are `auto`: a listener installed only when a spec happens to ask
  // for it is a listener that silently changes behaviour when it doesn't.
  // Playwright dismisses unhandled dialogs, the clock has to be frozen before
  // the first navigation, and every test starts from an empty database.
  api: [
    async ({ page }, use) => {
      const recorder = new NetworkRecorder(page, API_ORIGIN);
      await recorder.install();
      await installClock(page);
      await use(recorder);
    },
    { auto: true },
  ],

  dialogs: [
    async ({ page }, use) => {
      const recorder = new DialogRecorder(page);
      recorder.install();
      await use(recorder);
      recorder.reset();
    },
    { auto: true },
  ],

  seed: [
    async ({ request }, use) => {
      const seeder = new Seeder(request, API_ORIGIN);
      await seeder.snapshot();
      await seeder.resetDb();
      await use(seeder);
      await seeder.resetDb();
    },
    { auto: true },
  ],

  settle: async ({ page }, use) => {
    await use((ms: number) => settleClock(page, ms));
  },
});

export { expect };
export { checkA11y } from './axe';
export { expectNoLiveTweens, expectOverlayFillsViewport } from './motion';
export { fillForm, typeInto } from './form';
export {
  BRRRR_FORM_FIELDS,
  BRRRR_PAYLOAD,
  FLIP_FORM_FIELDS,
  FLIP_PAYLOAD,
} from './payloads';
