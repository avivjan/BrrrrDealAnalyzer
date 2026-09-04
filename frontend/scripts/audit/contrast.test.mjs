import { describe, expect, it } from 'vitest';
import {
  CONTRAST_PAIRS,
  checkThemes,
  contrastRatio,
  parseTokens,
  relativeLuminance,
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
});

describe('the audited pair set', () => {
  it('holds the sixteen pairs, with 3:1 for the ring and 4.5:1 for text', () => {
    expect(CONTRAST_PAIRS).toHaveLength(16);
    for (const pair of CONTRAST_PAIRS) {
      expect(pair.min).toBe(pair.foreground === 'ring' ? 3 : 4.5);
    }
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

describe('the committed tokens.css', () => {
  it('passes every audited pair in both themes', () => {
    const result = run();
    expect(result.lines.filter((line) => line.status === 'FAIL')).toEqual([]);
    expect(result.ok).toBe(true);
  });
});
