import { describe, expect, it } from 'vitest';
import { HOVER_REVEAL, TOUCH_REVEAL, findUnpairedInSource } from './hover-pairs.mjs';

const FILE = 'src/components/Fixture.vue';

function sfc(template) {
  return `<script setup lang="ts">\nconst a = 1;\n</script>\n\n<template>\n${template}\n</template>\n`;
}

const check = (template) => findUnpairedInSource(sfc(template), FILE);

describe('G-HOVER hover/touch pairing', () => {
  it('names the two classes it pairs', () => {
    expect(HOVER_REVEAL).toBe('hover:opacity-100');
    expect(TOUCH_REVEAL).toBe('touch:opacity-100');
  });

  it('passes an element with no hover reveal at all', () => {
    expect(check('<div class="opacity-0 transition-opacity">x</div>')).toEqual([]);
  });

  it('passes a group-hover reveal paired with touch:opacity-100', () => {
    expect(
      check('<div class="opacity-0 group-hover:opacity-100 touch:opacity-100">x</div>'),
    ).toEqual([]);
  });

  it('passes a bare hover reveal paired with touch:opacity-100', () => {
    expect(check('<div class="opacity-0 hover:opacity-100 touch:opacity-100">x</div>')).toEqual([]);
  });

  it('fails an unpaired group-hover reveal', () => {
    const lines = check('<div class="opacity-0 group-hover:opacity-100">x</div>');
    expect(lines).toHaveLength(1);
    expect(lines[0].level).toBe('FAIL');
    expect(lines[0].text).toContain(`${FILE}:6`);
    expect(lines[0].text).toContain(TOUCH_REVEAL);
  });

  it('fails an unpaired bare hover reveal', () => {
    expect(check('<div class="opacity-0 hover:opacity-100">x</div>')).toHaveLength(1);
  });

  it('does not accept focus-within:opacity-100 as the touch counterpart', () => {
    const lines = check(
      '<div class="opacity-0 group-hover:opacity-100 focus-within:opacity-100">x</div>',
    );
    expect(lines).toHaveLength(1);
  });

  it('passes focus-within plus touch together', () => {
    expect(
      check(
        '<div class="opacity-0 group-hover:opacity-100 focus-within:opacity-100 touch:opacity-100">x</div>',
      ),
    ).toEqual([]);
  });

  it('checks a :class array literal', () => {
    expect(check(`<div :class="['group-hover:opacity-100']">x</div>`)).toHaveLength(1);
    expect(
      check(`<div :class="['group-hover:opacity-100', 'touch:opacity-100']">x</div>`),
    ).toEqual([]);
  });

  it('checks a :class ternary', () => {
    expect(check(`<div :class="a ? 'group-hover:opacity-100' : ''">x</div>`)).toHaveLength(1);
    expect(
      check(`<div :class="a ? 'group-hover:opacity-100 touch:opacity-100' : ''">x</div>`),
    ).toEqual([]);
  });

  it('checks a :class object literal', () => {
    expect(check(`<div :class="{ 'group-hover:opacity-100': a }">x</div>`)).toHaveLength(1);
  });

  it('pairs a static hover reveal with a bound touch counterpart on the same element', () => {
    expect(
      check(`<div class="group-hover:opacity-100" :class="{ 'touch:opacity-100': a }">x</div>`),
    ).toEqual([]);
  });

  it('never pairs across two different elements', () => {
    const lines = check(
      '<div class="touch:opacity-100"><span class="group-hover:opacity-100">x</span></div>',
    );
    expect(lines).toHaveLength(1);
    expect(lines[0].text).toContain(':6');
  });

  it('checks components and nested elements, and reports each site once', () => {
    const lines = check(
      [
        '<UiCard>',
        '  <UiIconButton class="opacity-0 group-hover:opacity-100" />',
        '  <span class="opacity-0 group-hover:opacity-100 touch:opacity-100">x</span>',
        '  <button class="opacity-0 hover:opacity-100">y</button>',
        '</UiCard>',
      ].join('\n'),
    );
    expect(lines).toHaveLength(2);
    expect(lines.map((line) => line.text.match(/:(\d+)/)[1])).toEqual(['7', '9']);
  });

  it('ignores a hover reveal written in a comment or a script block', () => {
    expect(check('<!-- group-hover:opacity-100 --><div>x</div>')).toEqual([]);
    expect(
      findUnpairedInSource(
        `<script setup lang="ts">\n// group-hover:opacity-100\n</script>\n<template>\n<div>x</div>\n</template>\n`,
        FILE,
      ),
    ).toEqual([]);
  });
});
