import { describe, expect, it } from 'vitest';
import { manifestFromSource, verifyBindings } from './bindings.mjs';

const EMPTY_ALLOWLIST = { scripts: [], bindings: [], text: [] };
const FILE = 'src/components/Fixture.vue';

function sfc(template, script = 'const a = 1;\nconst b = 2;') {
  return `<script setup lang="ts">\n${script}\n</script>\n\n<template>\n${template}\n</template>\n`;
}

function compare(beforeTemplate, afterTemplate, allowlist = EMPTY_ALLOWLIST, script) {
  return verifyBindings({
    golden: { [FILE]: manifestFromSource(sfc(beforeTemplate, script?.[0]), FILE) },
    current: { [FILE]: manifestFromSource(sfc(afterTemplate, script?.[1]), FILE) },
    allowlist,
  });
}

const fails = (result) => result.lines.filter((l) => l.level === 'FAIL');

describe('G4 behaviour manifest', () => {
  it('flags a renamed event handler as a changed entry', () => {
    const result = compare('<button @click="a">x</button>', '<button @click="b">x</button>');
    expect(result.ok).toBe(false);
    expect(fails(result).some((l) => l.text.includes('changed element'))).toBe(true);
  });

  it('ignores a new purely presentational wrapper element', () => {
    const result = compare(
      '<button @click="a">x</button>',
      '<div class="x"><button @click="a">x</button></div>',
    );
    expect(result.ok).toBe(true);
    expect(fails(result)).toEqual([]);
  });

  it('treats UiButton and UiIconButton as button', () => {
    expect(compare('<button @click="a">x</button>', '<UiButton @click="a">x</UiButton>').ok).toBe(true);
    expect(compare('<button @click="a">x</button>', '<UiIconButton @click="a">x</UiIconButton>').ok).toBe(true);
  });

  describe('presentational Ui* aliases', () => {
    it('accepts a div swapped for a presentational UiCard', () => {
      expect(compare('<div @click="a">x</div>', '<UiCard @click="a">x</UiCard>').ok).toBe(true);
    });

    it('accepts a section swapped for a presentational UiCard', () => {
      expect(compare('<section v-for="r in rows">x</section>', '<UiCard v-for="r in rows">x</UiCard>').ok).toBe(
        true,
      );
    });

    it('never aliases a native control: input -> UiField fails', () => {
      const result = compare('<input v-model="a" />', '<UiField v-model="a" />');
      expect(result.ok).toBe(false);
      expect(fails(result).some((l) => l.text.includes('changed element'))).toBe(true);
    });

    it('still compares bindings exactly under the alias', () => {
      const result = compare('<div @click="a">x</div>', '<UiCard @click="b">x</UiCard>');
      expect(result.ok).toBe(false);
      expect(fails(result).some((l) => l.text.includes('changed element'))).toBe(true);
    });

    it('never aliases an anchor: a[href] -> UiCard fails', () => {
      const result = compare('<a href="/x" @click="a">x</a>', '<UiCard href="/x" @click="a">x</UiCard>');
      expect(result.ok).toBe(false);
      expect(fails(result).some((l) => l.text.includes('changed element'))).toBe(true);
    });
  });

  it('treats a preset-only transition as a wrapper', () => {
    const result = compare(
      '<button @click="a">x</button>',
      '<UiTransition preset="modal" appear><button @click="a">x</button></UiTransition>',
    );
    expect(result.ok).toBe(true);
  });

  it('does not treat a transition carrying behaviour as a wrapper', () => {
    const result = compare(
      '<button @click="a">x</button>',
      '<UiTransition preset="modal" @after-leave="a"><button @click="a">x</button></UiTransition>',
    );
    expect(result.ok).toBe(false);
  });

  it('flags re-ordered v-else-if branches', () => {
    const before = '<div><p v-if="a">1</p><p v-else-if="b">2</p><p v-else-if="c">3</p><p v-else>4</p></div>';
    const after = '<div><p v-if="a">1</p><p v-else-if="c">3</p><p v-else-if="b">2</p><p v-else>4</p></div>';
    const result = compare(before, after);
    expect(result.ok).toBe(false);
  });

  it('records the chain identity and ordinal of every branch', () => {
    const manifest = manifestFromSource(
      sfc('<div><p v-if="a">1</p><p v-else-if="b">2</p><p v-else>3</p></div>'),
      FILE,
    );
    expect(manifest.elements.map((e) => e.bindings[0])).toEqual([
      { kind: 'if', arg: null, modifiers: [], expression: 'a', chain: 'a', chainIndex: 0 },
      { kind: 'else-if', arg: null, modifiers: [], expression: 'b', chain: 'a', chainIndex: 1 },
      { kind: 'else', arg: null, modifiers: [], expression: '', chain: 'a', chainIndex: 2 },
    ]);
  });

  it('fails an added v-if unless it is allowlisted', () => {
    const before = '<button @click="a">x</button>';
    const after = '<div v-if="showHalo" /><button @click="a">x</button>';
    expect(compare(before, after).ok).toBe(false);
    const allowed = compare(before, after, {
      ...EMPTY_ALLOWLIST,
      bindings: [{ file: FILE, expression: 'showHalo', reason: 'decorative halo' }],
    });
    expect(fails(allowed)).toEqual([]);
    expect(allowed.ok).toBe(true);
  });

  it('does not allow an added element that carries more than a v-if chain', () => {
    const result = compare('<button @click="a">x</button>', '<div v-if="showHalo" @click="a" /><button @click="a">x</button>', {
      ...EMPTY_ALLOWLIST,
      bindings: [{ file: FILE, expression: 'showHalo', reason: 'decorative halo' }],
    });
    expect(result.ok).toBe(false);
  });

  it('ignores class, data-* and library class attributes', () => {
    const before = '<div class="a" data-testid="t.one" ghost-class="g" :key="k" id="x" role="row" aria-label="l"><button @click="a">x</button></div>';
    const after = '<div class="b c" data-testid="t.two" ghost-class="h" :key="k" id="y" role="grid" aria-label="m"><button @click="a">x</button></div>';
    expect(compare(before, after).ok).toBe(true);
  });

  it('flags an added behavioural attribute such as type="button"', () => {
    const result = compare('<button @click="a">x</button>', '<button type="button" @click="a">x</button>');
    expect(result.ok).toBe(false);
  });

  it('records v-model, v-for, v-show and modifiers', () => {
    const manifest = manifestFromSource(
      sfc('<input v-model.number.trim="row.qty" v-show="open" @keyup.enter.stop="a" />'),
      FILE,
    );
    expect(manifest.elements[0].bindings).toEqual([
      { kind: 'model', arg: null, modifiers: ['number', 'trim'], expression: 'row.qty' },
      { kind: 'show', arg: null, modifiers: [], expression: 'open' },
      { kind: 'on', arg: 'keyup', modifiers: ['enter', 'stop'], expression: 'a' },
    ]);
  });

  it('skips valueless motion directives but records valued ones', () => {
    const bare = manifestFromSource(sfc('<div v-reveal class="x">t</div>'), FILE);
    expect(bare.elements).toEqual([]);
    const valued = manifestFromSource(sfc('<div v-reveal="opts" class="x">t</div>'), FILE);
    expect(valued.elements[0].bindings).toEqual([
      { kind: 'directive:reveal', arg: null, modifiers: [], expression: 'opts' },
    ]);
  });

  it('fails when a watch source or a lifecycle hook changes', () => {
    const watchBefore = 'watch(() => props.open, (v) => v);\nonMounted(() => 1);';
    const watchAfter = 'watch(() => props.closed, (v) => v);\nonMounted(() => 1);';
    const result = compare('<button @click="a">x</button>', '<button @click="a">x</button>', EMPTY_ALLOWLIST, [
      watchBefore,
      watchAfter,
    ]);
    expect(result.ok).toBe(false);
    expect(fails(result).some((l) => l.text.includes('watches'))).toBe(true);

    const hooks = compare('<button @click="a">x</button>', '<button @click="a">x</button>', EMPTY_ALLOWLIST, [
      watchBefore,
      'watch(() => props.open, (v) => v);\nonMounted(() => 1);\nonUnmounted(() => 2);',
    ]);
    expect(hooks.ok).toBe(false);
    expect(fails(hooks).some((l) => l.text.includes('hooks'))).toBe(true);
  });

  it('captures watch sources and hooks from the script text', () => {
    const manifest = manifestFromSource(
      sfc('<div>x</div>', 'watch(\n  () => props.a,\n  (v) => v,\n);\nwatchEffect(() => 1);\nonMounted(() => 2);\nonBeforeUnmount(() => 3);'),
      FILE,
    );
    expect(manifest.watches).toEqual(['() => props.a', '() => 1']);
    expect(manifest.hooks).toEqual(['onMounted', 'onBeforeUnmount']);
  });

  it('fails a deleted frozen file and reports a new file as INFO', () => {
    const manifest = manifestFromSource(sfc('<button @click="a">x</button>'), FILE);
    const result = verifyBindings({
      golden: { [FILE]: manifest },
      current: { 'src/components/New.vue': manifest },
      allowlist: EMPTY_ALLOWLIST,
    });
    expect(result.ok).toBe(false);
    expect(result.lines.some((l) => l.text.includes('deleted frozen file'))).toBe(true);
    expect(result.lines.some((l) => l.level === 'INFO' && l.text.includes('src/components/New.vue'))).toBe(true);
  });

  it('records a Teleport target as a behavioural attribute', () => {
    const manifest = manifestFromSource(sfc('<Teleport to="body"><div class="x">m</div></Teleport>'), FILE);
    expect(manifest.elements).toEqual([
      {
        tag: 'Teleport',
        line: 7,
        bindings: [{ kind: 'attr:to', arg: null, modifiers: [], expression: 'body' }],
      },
    ]);
  });

  it('flags a re-targeted Teleport', () => {
    const result = compare('<Teleport to="body"><div /></Teleport>', '<Teleport to="#app"><div /></Teleport>');
    expect(result.ok).toBe(false);
    expect(fails(result).some((l) => l.text.includes('attr:to'))).toBe(true);
  });
});

describe('G4 allowlist paths', () => {
  it('does not admit a branch-only addition through a row with no expression', () => {
    const result = compare('<button @click="a">x</button>', '<button @click="a">x</button><div v-else />', {
      ...EMPTY_ALLOWLIST,
      bindings: [{ file: FILE, reason: 'decorative' }],
    });
    expect(result.ok).toBe(false);
  });

  it('does not admit a branch-only addition through a row with an empty expression', () => {
    const result = compare('<button @click="a">x</button>', '<div v-if="halo" /><button @click="a">x</button>', {
      ...EMPTY_ALLOWLIST,
      bindings: [{ file: FILE, expression: '', reason: 'decorative' }],
    });
    expect(result.ok).toBe(false);
  });
});

describe('G4 routerview-transition-slot exemption', () => {
  const app = 'src/App.vue';
  const REWRITE =
    '<RouterView v-slot="{ Component }"><UiTransition preset="page" appear><component :is="Component" /></UiTransition></RouterView>';
  const row = (file) => ({
    ...EMPTY_ALLOWLIST,
    bindings: [{ file, reason: 'routerview-transition-slot' }],
  });

  function verifyApp(beforeTemplate, afterTemplate, allowlist, file = app) {
    return verifyBindings({
      golden: { [file]: manifestFromSource(sfc(beforeTemplate), file) },
      current: { [file]: manifestFromSource(sfc(afterTemplate), file) },
      allowlist,
    });
  }

  it('accepts exactly the approved App.vue rewrite when the row is present', () => {
    expect(verifyApp('<RouterView />', REWRITE, EMPTY_ALLOWLIST).ok).toBe(false);
    const allowed = verifyApp('<RouterView />', REWRITE, row(app));
    expect(fails(allowed)).toEqual([]);
    expect(allowed.ok).toBe(true);
  });

  it('rejects the rewrite when it smuggles in another element', () => {
    const result = verifyApp('<RouterView />', `${REWRITE}<div v-if="x" />`, row(app));
    expect(result.ok).toBe(false);
    expect(fails(result).some((l) => l.text.includes('added element'))).toBe(true);
  });

  it('never accepts a removal, even with the row present', () => {
    const result = verifyApp(
      `<div :title="t" /><RouterView />`,
      REWRITE,
      row(app),
    );
    expect(result.ok).toBe(false);
    expect(fails(result).some((l) => l.text.includes('removed element'))).toBe(true);
  });

  it('does not apply the exemption to any other file', () => {
    const other = 'src/views/MyDeals.vue';
    const result = verifyApp('<RouterView />', REWRITE, row(other), other);
    expect(result.ok).toBe(false);
  });

  it('does not compare line numbers', () => {
    const result = compare(
      '<button @click="a">x</button>',
      '<div class="pad">\n  <div class="pad">\n    <button @click="a">x</button>\n  </div>\n</div>',
    );
    expect(result.ok).toBe(true);
  });
});
