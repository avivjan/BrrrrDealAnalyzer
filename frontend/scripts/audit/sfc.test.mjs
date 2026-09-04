import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterAll, describe, expect, it } from 'vitest';
import { collapse, listSfcFiles, loadGolden, parseSfcSource } from './sfc.mjs';

const root = mkdtempSync(join(tmpdir(), 'audit-sfc-'));
afterAll(() => rmSync(root, { recursive: true, force: true }));

describe('listSfcFiles', () => {
  it('returns sorted, forward-slashed paths of every src/**/*.vue', () => {
    mkdirSync(join(root, 'src', 'components', 'ui'), { recursive: true });
    mkdirSync(join(root, 'src', 'views'), { recursive: true });
    writeFileSync(join(root, 'src', 'App.vue'), '<template><div /></template>');
    writeFileSync(join(root, 'src', 'views', 'Home.vue'), '<template><div /></template>');
    writeFileSync(join(root, 'src', 'components', 'ui', 'Btn.vue'), '<template><div /></template>');
    writeFileSync(join(root, 'src', 'main.ts'), 'export {};');
    expect(listSfcFiles(root)).toEqual([
      'src/App.vue',
      'src/components/ui/Btn.vue',
      'src/views/Home.vue',
    ]);
  });
});

describe('parseSfcSource', () => {
  it('throws rather than returning a partial descriptor for a malformed SFC', () => {
    expect(() => parseSfcSource('<template><div></template>', 'src/Bad.vue')).toThrow(/src\/Bad\.vue/);
  });
});

describe('collapse', () => {
  it('collapses whitespace runs and trims', () => {
    expect(collapse('  a \n\t b  ')).toBe('a b');
    expect(collapse(undefined)).toBe('');
  });
});

describe('loadGolden', () => {
  it('reports a missing golden as a failure instead of an empty baseline', () => {
    const result = loadGolden(join(root, 'nope.json'));
    expect(result.missing).toBe(true);
    expect(result.golden).toEqual({});
  });

  it('reads an existing golden', () => {
    const path = join(root, 'golden.json');
    writeFileSync(path, '{"src/App.vue":[]}');
    expect(loadGolden(path)).toEqual({ missing: false, golden: { 'src/App.vue': [] } });
  });
});
