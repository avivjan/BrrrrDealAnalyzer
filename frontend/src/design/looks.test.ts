import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

// The generator is plain ESM under scripts/; Vitest resolves it like any module.
import {
  LOOKS_DIR_URL,
  TOKEN_NAMES,
  declarations,
  renderLook,
} from "../../scripts/design/build-looks.mjs";
import { LOOKS as LOOK_DATA } from "../../scripts/design/looks.data.mjs";
import { DEFAULT_LOOK, LOOKS, type LookId } from "./looks";

type LookData = (typeof LOOK_DATA)[number];

const sheet = (id: string) => readFileSync(new URL(`${id}.css`, LOOKS_DIR_URL), "utf8");

/**
 * The names declared inside one rule block of a sheet. Finds the rule whose
 * selector list *starts with* `selector`, the same contract the contrast audit
 * relies on.
 */
function declaredIn(css: string, selector: string): Map<string, string> {
  const start = css.indexOf(`${selector},`);
  expect(start, `no rule starting with ${selector}`).toBeGreaterThanOrEqual(0);
  const open = css.indexOf("{", start);
  const close = css.indexOf("\n}", open);
  const found = new Map<string, string>();
  for (const match of css.slice(open, close).matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
    found.set(match[1]!, match[2]!.trim());
  }
  return found;
}

describe("the look sheets", () => {
  it("exist for every look, and the metadata lists every sheet", () => {
    expect(LOOK_DATA.map((look: LookData) => look.id).sort()).toEqual(
      LOOKS.map((look) => look.id).sort(),
    );
    expect(LOOKS.map((look) => look.id)).toContain(DEFAULT_LOOK);
  });

  it("mirror the data file's names and taglines", () => {
    for (const data of LOOK_DATA as LookData[]) {
      const meta = LOOKS.find((look) => look.id === (data.id as LookId));
      expect(meta, data.id).toBeDefined();
      expect(meta!.name).toBe(data.name);
      expect(meta!.tagline).toBe(data.tagline);
    }
  });

  it("are exactly what the generator produces from the data (run build-looks.mjs after editing looks.data.mjs)", () => {
    for (const data of LOOK_DATA as LookData[]) {
      expect(sheet(data.id), `${data.id}.css is stale`).toBe(renderLook(data));
    }
  });

  it.each((LOOK_DATA as LookData[]).map((look) => [look.id, look]))(
    "%s declares every token of the vocabulary in both its light and dark rule",
    (id, look) => {
      const css = sheet(id as string);
      const light = declaredIn(css, `[data-look="${id}"]`);
      const dark = declaredIn(css, `[data-look="${id}"].dark`);
      expect([...light.keys()]).toEqual(TOKEN_NAMES);
      expect([...dark.keys()]).toEqual(TOKEN_NAMES);
      // A look with identical page colours in both modes has no dark mode.
      expect(light.get("--color-page")).not.toBe(dark.get("--color-page"));
      // The chart literals must differ per mode too (the light/dark sets are derived separately).
      expect(light.get("--chart-bg")).not.toBe(dark.get("--chart-bg"));
      void look;
    },
  );

  it("write RGB triplets for every --color-* token so Tailwind can add alpha", () => {
    for (const data of LOOK_DATA as LookData[]) {
      for (const mode of ["light", "dark"] as const) {
        for (const [name, value] of declarations(data, mode) as [string, string][]) {
          if (name.startsWith("--color-")) expect(value, `${data.id} ${mode} ${name}`).toMatch(/^\d{1,3} \d{1,3} \d{1,3}$/);
          if (name.startsWith("--chart-")) expect(value, `${data.id} ${mode} ${name}`).toMatch(/^(#[0-9a-f]{6}|rgba?\([^)]*\))$/);
        }
      }
    }
  });

  it("never lets a look inherit a value from the base tokens", () => {
    // TOKEN_NAMES is the whole vocabulary a component may consume from a look;
    // a name missing here would silently fall through to tokens.css.
    for (const name of [
      "--color-surface-2", "--color-glass", "--glow-primary", "--blur-glass", "--border-w",
      "--font-display", "--gsap-ease-emphasized", "--ambient", "--chart-min-warning",
    ]) {
      expect(TOKEN_NAMES).toContain(name);
    }
  });
});
