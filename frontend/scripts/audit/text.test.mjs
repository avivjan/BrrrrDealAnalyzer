import { describe, expect, it } from 'vitest';
import { collectTextFromSource, verifyText } from './text.mjs';

const EMPTY_ALLOWLIST = { scripts: [], bindings: [], text: [] };
const FILE = 'src/views/Fixture.vue';

function sfc(template) {
  return `<script setup lang="ts">\nconst a = 1;\n</script>\n\n<template>\n${template}\n</template>\n`;
}

function compare(before, after, allowlist = EMPTY_ALLOWLIST) {
  return verifyText({
    golden: { [FILE]: collectTextFromSource(sfc(before), FILE) },
    current: { [FILE]: collectTextFromSource(sfc(after), FILE) },
    allowlist,
  });
}

describe('G4b copy freeze', () => {
  it('collects static text and interpolations in document order', () => {
    expect(
      collectTextFromSource(sfc('<div>My Deals<span>{{ store.count }} left</span></div>'), FILE),
    ).toEqual(['My Deals', '{{ store.count }}', 'left']);
  });

  it('ignores whitespace and indentation changes', () => {
    const result = compare(
      '<div><h1>My Deals</h1></div>',
      '<div class="grid">\n    <h1>\n      My   Deals\n    </h1>\n  </div>',
    );
    expect(result.ok).toBe(true);
    expect(result.lines.filter((l) => l.level === 'FAIL')).toEqual([]);
  });

  it('ignores comments and script/style text', () => {
    expect(collectTextFromSource(sfc('<div><!-- a note -->Hello</div>'), FILE)).toEqual(['Hello']);
    const withStyle = `<script setup lang="ts">\nconst label = "hidden";\n</script>\n<template><p>Shown</p></template>\n<style scoped>\n.a { content: "css text"; }\n</style>\n`;
    expect(collectTextFromSource(withStyle, FILE)).toEqual(['Shown']);
  });

  it('fails when a label word changes', () => {
    const result = compare('<h1>My Deals</h1>', '<h1>My Properties</h1>');
    expect(result.ok).toBe(false);
    expect(result.lines.some((l) => l.text.includes('My Deals') && l.text.includes('My Properties'))).toBe(true);
  });

  it('fails when an interpolation expression changes', () => {
    const result = compare('<p>{{ store.total }}</p>', '<p>{{ store.sum }}</p>');
    expect(result.ok).toBe(false);
  });

  it('passes an allowlisted from/to rewrite', () => {
    const result = compare('<h1>My Deals</h1>', '<h1>My Properties</h1>', {
      ...EMPTY_ALLOWLIST,
      text: [{ file: FILE, from: 'My Deals', to: 'My Properties', reason: 'approved copy change' }],
    });
    expect(result.lines.filter((l) => l.level === 'FAIL')).toEqual([]);
    expect(result.ok).toBe(true);
  });

  it('does not accept an allowlist entry whose from/to does not match exactly', () => {
    const result = compare('<h1>My Deals</h1>', '<h1>My Properties</h1>', {
      ...EMPTY_ALLOWLIST,
      text: [{ file: FILE, from: 'My Deals', to: 'My Portfolio', reason: 'wrong target' }],
    });
    expect(result.ok).toBe(false);
  });

  it('requires an allowlist entry for a pure addition or removal', () => {
    expect(compare('<h1>Deals</h1>', '<h1>Deals</h1><p>New tagline</p>').ok).toBe(false);
    expect(
      compare('<h1>Deals</h1>', '<h1>Deals</h1><p>New tagline</p>', {
        ...EMPTY_ALLOWLIST,
        text: [{ file: FILE, from: '', to: 'New tagline', reason: 'approved new copy' }],
      }).ok,
    ).toBe(true);
    expect(
      compare('<h1>Deals</h1><p>Old tagline</p>', '<h1>Deals</h1>', {
        ...EMPTY_ALLOWLIST,
        text: [{ file: FILE, from: 'Old tagline', to: '', reason: 'approved removal' }],
      }).ok,
    ).toBe(true);
  });

  it('fails a deleted frozen file and reports a new file as INFO', () => {
    const result = verifyText({
      golden: { [FILE]: ['Deals'] },
      current: { 'src/views/New.vue': ['Deals'] },
      allowlist: EMPTY_ALLOWLIST,
    });
    expect(result.ok).toBe(false);
    expect(result.lines.some((l) => l.text.includes('deleted frozen file'))).toBe(true);
    expect(result.lines.some((l) => l.level === 'INFO' && l.text.includes('src/views/New.vue'))).toBe(true);
  });
});
