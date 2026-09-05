import { describe, expect, it } from 'vitest';
import { entryFromSource, verifyScriptBlocks } from './script-blocks.mjs';

const EMPTY_ALLOWLIST = { scripts: [], bindings: [], text: [] };

function sfc(scriptSetup, template = '<template><div /></template>') {
  return `<script setup lang="ts">\n${scriptSetup}\n</script>\n\n${template}\n`;
}

/** Build the {file: entry} maps the verifier consumes, from inline SFC sources. */
function entries(map) {
  const out = {};
  for (const [file, source] of Object.entries(map)) out[file] = entryFromSource(source, file);
  return out;
}

function verify(goldenSources, currentSources, allowlist = EMPTY_ALLOWLIST) {
  return verifyScriptBlocks({
    golden: entries(goldenSources),
    current: entries(currentSources),
    allowlist,
  });
}

const BASE = sfc(`import { computed } from "vue";\n\nconst total = computed(() => 1 + 1);`);

describe('G3 script freeze', () => {
  it('passes when the script blocks are identical', () => {
    const result = verify({ 'src/A.vue': BASE }, { 'src/A.vue': BASE });
    expect(result.ok).toBe(true);
    expect(result.lines.filter((l) => l.level !== 'INFO')).toEqual([]);
  });

  it('passes an allowlisted useId line added after the last baseline line', () => {
    const after = sfc(
      `import { computed } from "vue";\n\nconst total = computed(() => 1 + 1);\nconst panelId = useId();`,
    );
    const result = verify({ 'src/A.vue': BASE }, { 'src/A.vue': after }, {
      ...EMPTY_ALLOWLIST,
      scripts: [{ file: 'src/A.vue', reason: 'useId for aria wiring' }],
    });
    expect(result.lines.filter((l) => l.level === 'FAIL')).toEqual([]);
    expect(result.ok).toBe(true);
  });

  it('fails an accepted diff that is not in the allowlist', () => {
    const after = sfc(
      `import { computed } from "vue";\n\nconst total = computed(() => 1 + 1);\nconst panelId = useId();`,
    );
    const result = verify({ 'src/A.vue': BASE }, { 'src/A.vue': after });
    expect(result.ok).toBe(false);
    expect(result.lines.some((l) => l.text.includes('unlisted script change'))).toBe(true);
  });

  it('warns for an allowlist entry that has no diff', () => {
    const result = verify({ 'src/A.vue': BASE }, { 'src/A.vue': BASE }, {
      ...EMPTY_ALLOWLIST,
      scripts: [{ file: 'src/A.vue', reason: 'stale' }],
    });
    expect(result.ok).toBe(true);
    expect(result.lines.some((l) => l.level === 'WARN')).toBe(true);
  });

  it('does not warn about an allowlist entry when the diff itself is rejected', () => {
    const after = sfc(`import { computed } from "vue";\n\nconst total = computed(() => 1 + 1);\nconst x = 1;`);
    const result = verify({ 'src/A.vue': BASE }, { 'src/A.vue': after }, {
      ...EMPTY_ALLOWLIST,
      scripts: [{ file: 'src/A.vue', reason: 'attempted' }],
    });
    expect(result.ok).toBe(false);
    expect(result.lines.filter((l) => l.level === 'WARN')).toEqual([]);
  });

  it('fails when an existing line is edited (removed line)', () => {
    const after = sfc(`import { computed } from "vue";\n\nconst total = computed(() => 1 + 2);`);
    const result = verify({ 'src/A.vue': BASE }, { 'src/A.vue': after });
    expect(result.ok).toBe(false);
    expect(result.lines.some((l) => l.text.includes('removed line'))).toBe(true);
  });

  it('allows a blank separator line before an allowed appended line', () => {
    const after = sfc(
      `import { computed } from "vue";\n\nconst total = computed(() => 1 + 1);\n\nconst panelRef = ref<HTMLElement | null>(null);`,
    );
    const result = verify({ 'src/A.vue': BASE }, { 'src/A.vue': after }, {
      ...EMPTY_ALLOWLIST,
      scripts: [{ file: 'src/A.vue', reason: 'template ref for the panel' }],
    });
    expect(result.lines.filter((l) => l.level === 'FAIL')).toEqual([]);
    expect(result.ok).toBe(true);
  });

  it('fails an added line that matches no allowed pattern', () => {
    const after = sfc(
      `import { computed } from "vue";\n\nconst total = computed(() => 1 + 1);\nconst x = 1;`,
    );
    const result = verify({ 'src/A.vue': BASE }, { 'src/A.vue': after });
    expect(result.ok).toBe(false);
    expect(result.lines.some((l) => l.text.includes('added line not allowed'))).toBe(true);
  });

  it('fails an allowed-pattern line inserted in the middle of the block', () => {
    const before = sfc(`const a = 1;\nconst b = 2;\nconst c = 3;`);
    const after = sfc(`const a = 1;\nconst headingId = useId();\nconst b = 2;\nconst c = 3;`);
    const result = verify({ 'src/A.vue': before }, { 'src/A.vue': after }, {
      ...EMPTY_ALLOWLIST,
      scripts: [{ file: 'src/A.vue', reason: 'useId' }],
    });
    expect(result.ok).toBe(false);
    expect(result.lines.some((l) => l.text.includes('misplaced'))).toBe(true);
  });

  it('accepts an allowed import added inside the import block', () => {
    const before = sfc(`import { computed } from "vue";\n\nconst total = computed(() => 1);`);
    const after = sfc(
      `import { computed } from "vue";\nimport { ref } from "vue";\n\nconst total = computed(() => 1);`,
    );
    const result = verify({ 'src/A.vue': before }, { 'src/A.vue': after }, {
      ...EMPTY_ALLOWLIST,
      scripts: [{ file: 'src/A.vue', reason: 'ref for a template ref' }],
    });
    expect(result.ok).toBe(true);
  });

  it('accepts the E1 chartToken substitution in TimelineChart.vue', () => {
    const file = 'src/components/liquidity/TimelineChart.vue';
    const before = sfc(`function draw(ctx) {\n  ctx.fillStyle = '#0f1117'\n}`);
    const after = sfc(
      `import { chartToken } from "../../design/chartTokens";\nfunction draw(ctx) {\n  ctx.fillStyle = chartToken('bg')\n}`,
    );
    const result = verify({ [file]: before }, { [file]: after }, {
      ...EMPTY_ALLOWLIST,
      scripts: [{ file, reason: 'E1 chart token substitution' }],
    });
    expect(result.lines.filter((l) => l.level === 'FAIL')).toEqual([]);
    expect(result.ok).toBe(true);
  });

  it('rejects the same chartToken substitution in any other file', () => {
    const file = 'src/components/liquidity/OtherChart.vue';
    const before = sfc(`function draw(ctx) {\n  ctx.fillStyle = '#0f1117'\n}`);
    const after = sfc(`function draw(ctx) {\n  ctx.fillStyle = chartToken('bg')\n}`);
    const result = verify({ [file]: before }, { [file]: after }, {
      ...EMPTY_ALLOWLIST,
      scripts: [{ file, reason: 'not exempt' }],
    });
    expect(result.ok).toBe(false);
    expect(result.lines.some((l) => l.text.includes('removed line'))).toBe(true);
  });

  it('fails when a frozen file disappears and reports new files as INFO', () => {
    const result = verify({ 'src/A.vue': BASE }, { 'src/B.vue': BASE });
    expect(result.ok).toBe(false);
    expect(result.lines.some((l) => l.text.includes('deleted frozen file'))).toBe(true);
    expect(result.lines.some((l) => l.level === 'INFO' && l.text.includes('src/B.vue'))).toBe(true);
  });

  it('ignores trailing whitespace', () => {
    const after = sfc(`import { computed } from "vue";   \n\nconst total = computed(() => 1 + 1);\t`);
    const result = verify({ 'src/A.vue': BASE }, { 'src/A.vue': after });
    expect(result.ok).toBe(true);
  });

  it('freezes a plain (non-setup) script block too', () => {
    const before = `<script lang="ts">\nexport default { name: "A" };\n</script>\n<template><div /></template>\n`;
    const after = `<script lang="ts">\nexport default { name: "B" };\n</script>\n<template><div /></template>\n`;
    const result = verify({ 'src/A.vue': before }, { 'src/A.vue': after });
    expect(result.ok).toBe(false);
    expect(result.lines.some((l) => /\[script L\d+\] removed line/.test(l.text))).toBe(true);
  });
});
