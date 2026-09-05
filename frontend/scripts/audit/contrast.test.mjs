import { describe, expect, it } from 'vitest';
import {
  CONTRAST_PAIRS,
  checkThemes,
  contrastRatio,
  lookThemes,
  parseLook,
  parseTokens,
  relativeLuminance,
  ruleBody,
  run,
} from './contrast.mjs';

const BLACK = [0, 0, 0];
const WHITE = [255, 255, 255];

const FIXTURE = `
:root {
  --color-page: 255 255 255;
  --color-surface: 255 255 255;
  --color-surface-muted: 255 255 255;
  --color-fg: 0 0 0;
  --color-fg-muted: 118 118 118;
  --color-primary: 0 0 0;
  --color-primary-hover: 0 0 0;
  --color-primary-fg: 255 255 255;
  --color-positive: 0 0 0;
  --color-negative: 0 0 0;
  --color-warning: 0 0 0;
  --color-ring: 0 0 0;
  --color-surface-2: 255 255 255;
  --color-surface-3: 255 255 255;
  --color-accent: 0 0 0;
  --radius-sm: 6px;
  --chart-bg: #0f1117;
}
.dark {
  --color-page: 0 0 0;
  --color-surface: 0 0 0;
  --color-surface-muted: 0 0 0;
  --color-fg: 255 255 255;
  --color-fg-muted: 255 255 255;
  --color-primary: 255 255 255;
  --color-primary-hover: 255 255 255;
  --color-primary-fg: 0 0 0;
  --color-positive: 255 255 255;
  --color-negative: 255 255 255;
  --color-warning: 255 255 255;
  --color-ring: 255 255 255;
  --color-surface-2: 0 0 0;
  --color-surface-3: 0 0 0;
  --color-accent: 255 255 255;
}
`;

describe('WCAG contrast maths', () => {
  it('gives white a luminance of 1 and black a luminance of 0', () => {
    expect(relativeLuminance(WHITE)).toBeCloseTo(1, 10);
    expect(relativeLuminance(BLACK)).toBeCloseTo(0, 10);
  });

  it('rates black on white at 21:1, in either order', () => {
    expect(contrastRatio(BLACK, WHITE)).toBeCloseTo(21, 5);
    expect(contrastRatio(WHITE, BLACK)).toBeCloseTo(21, 5);
  });

  it('rates the AA borderline grey #767676 on white at 4.54:1', () => {
    expect(contrastRatio([118, 118, 118], WHITE)).toBeCloseTo(4.54, 2);
  });

  it('rates a colour against itself at 1:1', () => {
    expect(contrastRatio([79, 70, 229], [79, 70, 229])).toBeCloseTo(1, 10);
  });
});

describe('token parsing', () => {
  it('reads the --color-* triplets of :root and .dark', () => {
    const themes = parseTokens(FIXTURE);
    expect(themes.light['color-fg']).toEqual([0, 0, 0]);
    expect(themes.light['color-fg-muted']).toEqual([118, 118, 118]);
    expect(themes.dark['color-fg']).toEqual([255, 255, 255]);
  });

  it('ignores non-colour tokens and resolved colour strings', () => {
    const themes = parseTokens(FIXTURE);
    expect(themes.light['radius-sm']).toBeUndefined();
    expect(themes.light['chart-bg']).toBeUndefined();
  });

  it('reads past a nested at-rule instead of stopping at its closing brace', () => {
    const nested = `
:root {
  --color-page: 255 255 255;
  @supports (color: rgb(0 0 0 / 1)) {
    --color-surface: 240 240 240;
  }
  --color-fg: 0 0 0;
}
`;
    const themes = parseTokens(nested);
    expect(themes.light['color-page']).toEqual([255, 255, 255]);
    expect(themes.light['color-surface']).toEqual([240, 240, 240]);
    // Declared *after* the nested block — a naive "first }" scan loses this one.
    expect(themes.light['color-fg']).toEqual([0, 0, 0]);
  });

  it('does not mistake a longer selector such as .darker for .dark', () => {
    const decoy = `
:root { --color-fg: 0 0 0; }
.darker { --color-fg: 1 1 1; }
.dark { --color-fg: 255 255 255; }
`;
    expect(parseTokens(decoy).dark['color-fg']).toEqual([255, 255, 255]);
  });

  it('does not mistake a compound selector such as .theme.dark for .dark', () => {
    const compound = `
:root { --color-fg: 0 0 0; }
.theme.dark { --color-fg: 2 2 2; }
.dark { --color-fg: 255 255 255; }
`;
    expect(parseTokens(compound).dark['color-fg']).toEqual([255, 255, 255]);
  });

  it('returns nothing for a theme whose rule is absent', () => {
    expect(parseTokens(':root { --color-fg: 0 0 0; }').dark).toEqual({});
  });
});

describe('the audited pair set', () => {
  it('holds the twenty-seven pairs, with 3:1 for the non-text ring and primary boundary and 4.5:1 for text', () => {
    expect(CONTRAST_PAIRS).toHaveLength(27);
    for (const pair of CONTRAST_PAIRS) {
      const nonText = pair.foreground === 'ring' || (pair.foreground === 'primary' && pair.background === 'surface');
      expect(pair.min, `${pair.foreground} on ${pair.background}`).toBe(nonText ? 3 : 4.5);
    }
  });
});

describe('look sheets', () => {
  const sheet = `
/* generated */
[data-look="mono"],
[data-look="mono"][data-mode="light"],
.dark [data-look="mono"][data-mode="light"] {
  --color-fg: 1 1 1;
  --color-page: 255 255 255;
}
[data-look="mono"].dark,
.dark [data-look="mono"],
[data-look="mono"][data-mode="dark"] {
  --color-fg: 254 254 254;
  --color-page: 5 5 5;
}
`;

  it('names a light and a dark set per look', () => {
    expect(lookThemes('mono')).toEqual([
      { name: 'mono-light', selector: '[data-look="mono"]' },
      { name: 'mono-dark', selector: '[data-look="mono"].dark' },
    ]);
  });

  it('reads the block whose selector list starts with the selector, even with more selectors after it', () => {
    expect(ruleBody(sheet, '[data-look="mono"]')).toContain('--color-fg: 1 1 1');
    expect(ruleBody(sheet, '[data-look="mono"].dark')).toContain('--color-fg: 254 254 254');
  });

  it('does not mistake the dark list, which mentions the bare selector later, for the light block', () => {
    const darkFirst = sheet.slice(sheet.indexOf('[data-look="mono"].dark'));
    // Only the dark rule is present: the bare selector appears inside its list, not at its start.
    expect(ruleBody(darkFirst, '[data-look="mono"]')).toBe('');
  });

  it('parses both sets of a look', () => {
    const themes = parseLook(sheet, 'mono');
    expect(themes['mono-light']['color-fg']).toEqual([1, 1, 1]);
    expect(themes['mono-light']['color-page']).toEqual([255, 255, 255]);
    expect(themes['mono-dark']['color-page']).toEqual([5, 5, 5]);
  });

  it('audits the named sets on top of the base light set', () => {
    const base = parseTokens(FIXTURE);
    const themes = { ...base, ...parseLook(sheet, 'mono') };
    const result = checkThemes(themes, ['mono-light', 'mono-dark']);
    expect(new Set(result.lines.map((line) => line.theme))).toEqual(new Set(['mono-light', 'mono-dark']));
    // The light set only re-declares fg and page; everything else inherits the
    // black-on-white base and passes.
    expect(result.lines.filter((line) => line.theme === 'mono-light').every((line) => line.status === 'PASS')).toBe(true);
    // The dark set inherits the *light* base too — that is what the browser
    // does when a look omits a token — so its near-white fg lands on the base's
    // white surface and fails. This is why the generator writes every token
    // into both blocks.
    const darkFailures = result.lines.filter((line) => line.theme === 'mono-dark' && line.status === 'FAIL');
    expect(darkFailures.map((line) => `${line.foreground}/${line.background}`)).toContain('fg/surface');
    expect(result.ok).toBe(false);
  });
});

describe('checkThemes', () => {
  const themes = parseTokens(FIXTURE);

  it('passes a fixture built from black and white', () => {
    const result = checkThemes(themes);
    expect(result.ok).toBe(true);
    expect(result.lines).toHaveLength(CONTRAST_PAIRS.length * 2);
    expect(result.lines.every((line) => line.status === 'PASS')).toBe(true);
  });

  it('reports one line per pair per theme, with the measured ratio', () => {
    const line = checkThemes(themes).lines.find(
      (candidate) => candidate.theme === 'light' && candidate.foreground === 'fg',
    );
    expect(line.background).toBe('page');
    expect(line.ratio).toBeCloseTo(21, 5);
    expect(line.text).toContain('light');
    expect(line.text).toContain('fg on page');
    expect(line.text).toContain('21');
  });

  it('fails a pair below its threshold and keeps checking the rest', () => {
    const failing = {
      light: { ...themes.light, 'color-fg-muted': [170, 170, 170] },
      dark: themes.dark,
    };
    const result = checkThemes(failing);
    expect(result.ok).toBe(false);
    const failures = result.lines.filter((line) => line.status === 'FAIL');
    expect(failures.map((line) => `${line.foreground}/${line.background}`)).toEqual([
      'fg-muted/page',
      'fg-muted/surface',
      'fg-muted/surface-muted',
      'fg-muted/surface-2',
      'fg-muted/surface-3',
    ]);
  });

  it('holds the ring to 3:1 rather than 4.5:1', () => {
    // #949494 on white is 3.03:1 — enough for a ring, not for text.
    const ringOnly = {
      light: { ...themes.light, 'color-ring': [148, 148, 148] },
      dark: themes.dark,
    };
    expect(checkThemes(ringOnly).ok).toBe(true);
  });

  it('fails loudly when a token the pairs need is missing', () => {
    const missing = { light: { ...themes.light }, dark: themes.dark };
    delete missing.light['color-warning'];
    const result = checkThemes(missing);
    expect(result.ok).toBe(false);
    expect(result.lines.some((line) => line.text.includes('missing'))).toBe(true);
  });
});

describe('the committed tokens.css and look sheets', () => {
  it('passes every audited pair in every set', () => {
    const result = run();
    expect(result.lines.filter((line) => line.status === 'FAIL')).toEqual([]);
    expect(result.ok).toBe(true);
  });
});
