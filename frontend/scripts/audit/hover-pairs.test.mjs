import { describe, expect, it } from 'vitest';
import { REVEAL_PAIRS, classTokens, findUnpairedInSource } from './hover-pairs.mjs';

const FILE = 'src/components/Fixture.vue';
const TOUCH_REVEAL = 'touch:opacity-100';

function sfc(template) {
  return `<script setup lang="ts">\nconst a = 1;\n</script>\n\n<template>\n${template}\n</template>\n`;
}

const check = (template) => findUnpairedInSource(sfc(template), FILE);

describe('G-HOVER hover/touch pairing', () => {
  it('pairs each reveal with its own counterpart', () => {
    expect(REVEAL_PAIRS).toContainEqual(['hover:opacity-100', TOUCH_REVEAL]);
    for (const [reveal, counterpart] of REVEAL_PAIRS) {
      expect(reveal.startsWith('hover:')).toBe(true);
      expect(counterpart).toBe(reveal.replace('hover:', 'touch:'));
    }
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

  /**
   * One literal case per pair, written out rather than generated from
   * `REVEAL_PAIRS`: a table-driven loop mutates with the table, so deleting a
   * row would silently delete its own test.
   */
  describe('every reveal in the table', () => {
    it('fails an unpaired group-hover:visible, and passes it with touch:visible', () => {
      const lines = check('<div class="invisible group-hover:visible">x</div>');
      expect(lines).toHaveLength(1);
      expect(lines[0].text).toContain('touch:visible');
      expect(check('<div class="invisible group-hover:visible touch:visible">x</div>')).toEqual([]);
    });

    it('fails an unpaired group-hover:flex, and passes it with touch:flex', () => {
      const lines = check('<div class="hidden group-hover:flex">x</div>');
      expect(lines).toHaveLength(1);
      expect(lines[0].text).toContain('touch:flex');
      expect(check('<div class="hidden group-hover:flex touch:flex">x</div>')).toEqual([]);
    });

    it('fails an unpaired group-hover:block, and passes it with touch:block', () => {
      const lines = check('<div class="hidden group-hover:block">x</div>');
      expect(lines).toHaveLength(1);
      expect(lines[0].text).toContain('touch:block');
      expect(check('<div class="hidden group-hover:block touch:block">x</div>')).toEqual([]);
    });

    it('fails an unpaired group-hover:inline-flex, and passes it with touch:inline-flex', () => {
      const lines = check('<div class="hidden group-hover:inline-flex">x</div>');
      expect(lines).toHaveLength(1);
      expect(lines[0].text).toContain('touch:inline-flex');
      expect(
        check('<div class="hidden group-hover:inline-flex touch:inline-flex">x</div>'),
      ).toEqual([]);
    });

    it('fails an unpaired group-hover:pointer-events-auto, and passes it with its counterpart', () => {
      const lines = check(
        '<div class="pointer-events-none group-hover:pointer-events-auto">x</div>',
      );
      expect(lines).toHaveLength(1);
      expect(lines[0].text).toContain('touch:pointer-events-auto');
      expect(
        check(
          '<div class="pointer-events-none group-hover:pointer-events-auto touch:pointer-events-auto">x</div>',
        ),
      ).toEqual([]);
    });

    it('never accepts another pair’s counterpart', () => {
      const lines = check('<div class="hidden group-hover:flex touch:opacity-100">x</div>');
      expect(lines).toHaveLength(1);
      expect(lines[0].text).toContain('touch:flex');
    });

    it('names every missing counterpart on one element in one line', () => {
      const lines = check('<div class="group-hover:opacity-100 group-hover:flex">x</div>');
      expect(lines).toHaveLength(1);
      expect(lines[0].text).toContain('touch:opacity-100');
      expect(lines[0].text).toContain('touch:flex');
    });
  });

  describe('token anchoring', () => {
    it('splits class text on whitespace and quotes', () => {
      expect(classTokens(`{ 'touch:opacity-100': a }`)).toContain('touch:opacity-100');
      expect(classTokens('a  b\n c')).toEqual(['a', 'b', 'c']);
    });

    it('does not accept md:touch:opacity-100 as the counterpart', () => {
      const lines = check('<div class="group-hover:opacity-100 md:touch:opacity-100">x</div>');
      expect(lines).toHaveLength(1);
      expect(lines[0].text).toContain(TOUCH_REVEAL);
    });

    it('does not accept touch:opacity-100/50 as the counterpart', () => {
      expect(check('<div class="group-hover:opacity-100 touch:opacity-100/50">x</div>')).toHaveLength(1);
    });

    it('accepts a responsive reveal, which still needs the counterpart', () => {
      expect(check('<div class="md:group-hover:opacity-100">x</div>')).toHaveLength(1);
      expect(check('<div class="md:group-hover:opacity-100 touch:opacity-100">x</div>')).toEqual([]);
    });

    it('accepts peer-hover as a reveal', () => {
      expect(check('<div class="peer-hover:opacity-100">x</div>')).toHaveLength(1);
    });

    it('does not read hover:flex-col as a hover:flex reveal', () => {
      expect(check('<div class="hover:flex-col">x</div>')).toEqual([]);
    });

    it('does not read hover:invisible as a hover:visible reveal', () => {
      expect(check('<div class="hover:invisible">x</div>')).toEqual([]);
    });

    it('does not read hover:inline-flex as a hover:flex reveal', () => {
      const lines = check('<div class="hover:inline-flex">x</div>');
      expect(lines).toHaveLength(1);
      expect(lines[0].text).toContain('touch:inline-flex');
      expect(lines[0].text).not.toContain('touch:flex,');
    });
  });
});
