import { expect, type Dialog, type Page } from '@playwright/test';

/**
 * Native dialog recorder.
 *
 * The app leans on `window.confirm` / `window.alert` for every destructive
 * action, so the exact wording of those strings is part of the behaviour this
 * phase freezes. Playwright auto-dismisses dialogs when nothing is listening,
 * which would silently turn every "are you sure?" into "no" — so the recorder
 * accepts by default and the spec opts out per-case.
 */
export class DialogRecorder {
  readonly messages: string[] = [];
  private accepting = true;

  constructor(private readonly page: Page) {}

  install(): void {
    this.page.on('dialog', (dialog: Dialog) => this.onDialog(dialog));
  }

  private async onDialog(dialog: Dialog): Promise<void> {
    this.messages.push(dialog.message());
    if (this.accepting) await dialog.accept().catch(() => {});
    else await dialog.dismiss().catch(() => {});
  }

  /** Answer the next dialogs with Cancel instead of OK. */
  setAccept(accept: boolean): void {
    this.accepting = accept;
  }

  reset(): void {
    this.messages.length = 0;
    this.accepting = true;
  }

  /** Exact strings, in order. */
  async expectDialogs(expected: string[]): Promise<void> {
    await expect
      .poll(() => this.messages.length, { message: 'dialog count' })
      .toBe(expected.length);
    expect(this.messages).toEqual(expected);
  }
}
