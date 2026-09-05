import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
  BASELINE_TAG,
  E2E_FROZEN_PATHS,
  G1_PATHSPEC,
  G2_FROZEN_PATHS,
  GOLDEN_POLICY_PATHS,
  PHASE_PLAYWRIGHT_PROJECTS,
  e2eFreezeChecks,
  findGoldenPolicyViolations,
  findGoldenScopeViolations,
  gateLine,
  goldenPolicyGate,
  isGoldenPath,
} from './verify-ui.mjs';

describe('verify:ui pathspecs', () => {
  it('excludes the frontend, docs, scratch trees and the two setup docs from G1', () => {
    expect(G1_PATHSPEC).toEqual([
      '.',
      ':!frontend',
      ':!docs',
      ':!design-system',
      ':!.superpowers',
      ':!**/__pycache__/**',
      ':!REPS_README.md',
      ':!README.md',
    ]);
  });

  it('puts every golden path — manifests, e2e goldens, allowlist, archives — under the policy', () => {
    expect(GOLDEN_POLICY_PATHS).toEqual([
      'frontend/scripts/audit/golden',
      'frontend/e2e/golden',
      'frontend/scripts/audit/allowlist.json',
      'frontend/e2e/reports',
    ]);
  });

  it('freezes every non-presentational frontend directory in G2', () => {
    expect(G2_FROZEN_PATHS).toEqual([
      'frontend/src/stores',
      'frontend/src/api',
      'frontend/src/utils',
      'frontend/src/router',
      'frontend/src/types',
      'frontend/src/config',
    ]);
  });
});

describe('G2 e2e freeze (ui-p0)', () => {
  it('adds no e2e check while the ui-p0 tag does not exist', () => {
    expect(e2eFreezeChecks({ tagExists: () => false })).toEqual([]);
  });

  it('freezes the e2e flows and fixtures once ui-p0 exists', () => {
    expect(e2eFreezeChecks({ tagExists: (tag) => tag === 'ui-p0' })).toEqual([
      { ref: 'ui-p0', paths: E2E_FROZEN_PATHS },
    ]);
  });
});

describe('golden policy', () => {
  const log = [
    'aaa1111\tGolden update: Phase 1 baseline manifests',
    'bbb2222\tStep 1.3: restyle the deal card',
    'ccc3333\tGolden update: re-record bindings',
  ].join('\n');

  it('flags every non-"Golden update:" commit that touched a golden path', () => {
    expect(findGoldenPolicyViolations(log)).toEqual([
      { sha: 'bbb2222', subject: 'Step 1.3: restyle the deal card' },
    ]);
  });

  it('accepts a log where every commit is a golden update', () => {
    expect(findGoldenPolicyViolations('aaa1111\tGolden update: x')).toEqual([]);
    expect(findGoldenPolicyViolations('')).toEqual([]);
  });

  it('skips while the ui-p0 tag does not exist', () => {
    const gate = goldenPolicyGate({ tagExists: () => false, gitLog: () => '' });
    expect(gate.status).toBe('SKIP');
  });

  it('passes when ui-p0 exists and no offending commit is found', () => {
    const gate = goldenPolicyGate({
      tagExists: () => true,
      gitLog: () => 'aaa1111\tGolden update: x',
      gitFiles: () => ['frontend/e2e/golden/network-contract.json'],
    });
    expect(gate.status).toBe('PASS');
  });

  it('fails and names the offending commit', () => {
    const gate = goldenPolicyGate({
      tagExists: () => true,
      gitLog: () => log,
      gitFiles: () => [],
    });
    expect(gate.status).toBe('FAIL');
    expect(gate.detail).toContain('bbb2222');
  });

  it('queries the golden paths of ui-p0..HEAD and then the whole branch', () => {
    const calls = [];
    goldenPolicyGate({
      tagExists: () => true,
      gitLog: (range, paths) => {
        calls.push({ range, paths });
        return '';
      },
      gitFiles: () => [],
    });
    expect(calls).toEqual([
      { range: 'ui-p0..HEAD', paths: GOLDEN_POLICY_PATHS },
      { range: `${BASELINE_TAG}..HEAD`, paths: [] },
    ]);
  });
});

/**
 * The other half of the policy. The first half asks "did anything touch a
 * golden outside a `Golden update:` commit?"; without this one, a commit could
 * simply *say* `Golden update:` and smuggle a source change past every gate,
 * because the path-filtered log the first half reads never looks at the rest of
 * the commit.
 */
describe('golden policy — "Golden update:" commits carry nothing else', () => {
  it('recognises a golden path by exact name or directory prefix', () => {
    expect(isGoldenPath('frontend/scripts/audit/allowlist.json')).toBe(true);
    expect(isGoldenPath('frontend/e2e/reports/phase5-final.json')).toBe(true);
    expect(isGoldenPath('frontend/scripts/audit/golden/bindings.json')).toBe(true);
    // A lookalike sibling is not a golden.
    expect(isGoldenPath('frontend/scripts/audit/allowlist.json.bak')).toBe(false);
    expect(isGoldenPath('frontend/e2e/reports-old/phase5.json')).toBe(false);
    expect(isGoldenPath('frontend/src/views/MyDeals.vue')).toBe(false);
  });

  it('names every non-golden file a golden commit carried', () => {
    const violations = findGoldenScopeViolations([
      {
        sha: 'aaa1111',
        subject: 'Golden update: re-archive phase5-final.json',
        files: ['frontend/e2e/reports/phase5-final.json', 'frontend/src/views/MyDeals.vue'],
      },
      {
        sha: 'ccc3333',
        subject: 'Golden update: allowlist row',
        files: ['frontend/scripts/audit/allowlist.json'],
      },
    ]);
    expect(violations).toEqual([
      expect.objectContaining({ sha: 'aaa1111', extra: ['frontend/src/views/MyDeals.vue'] }),
    ]);
  });

  it('fails the gate and names the smuggled file', () => {
    const gate = goldenPolicyGate({
      tagExists: () => true,
      gitLog: (_range, paths) =>
        paths.length > 0 ? '' : 'aaa1111\tGolden update: re-archive phase5-final.json',
      gitFiles: () => ['frontend/e2e/reports/phase5-final.json', 'frontend/src/api/index.ts'],
    });
    expect(gate.status).toBe('FAIL');
    expect(gate.detail).toContain('aaa1111');
    expect(gate.detail).toContain('frontend/src/api/index.ts');
  });

  it('passes and counts the golden commits it checked', () => {
    const gate = goldenPolicyGate({
      tagExists: () => true,
      gitLog: (_range, paths) =>
        paths.length > 0
          ? ''
          : ['aaa1111\tGolden update: one', 'bbb2222\tStep 1.3: restyle', 'ccc3333\tGolden update: two'].join(
              '\n',
            ),
      gitFiles: () => ['frontend/e2e/golden/axe-baseline.json'],
    });
    expect(gate.status).toBe('PASS');
    expect(gate.detail).toContain('2 "Golden update:" commits');
  });

  it('never asks git for the files of an ordinary commit', () => {
    const asked = [];
    goldenPolicyGate({
      tagExists: () => true,
      gitLog: (_range, paths) => (paths.length > 0 ? '' : 'bbb2222\tStep 1.3: restyle the deal card'),
      gitFiles: (sha) => {
        asked.push(sha);
        return [];
      },
    });
    expect(asked).toEqual([]);
  });

  it('falls back to the ui-p0 range when the baseline tag is gone', () => {
    const calls = [];
    goldenPolicyGate({
      tagExists: (tag) => tag === 'ui-p0',
      gitLog: (range, paths) => {
        calls.push({ range, paths });
        return '';
      },
      gitFiles: () => [],
    });
    expect(calls.map((call) => call.range)).toEqual(['ui-p0..HEAD', 'ui-p0..HEAD']);
  });
});

describe('gate lines', () => {
  it('prints status first so the log greps cleanly', () => {
    expect(gateLine('PASS', 'G1', 'backend + root files unchanged since ui-baseline')).toBe(
      'PASS G1 backend + root files unchanged since ui-baseline',
    );
    expect(gateLine('SKIP', 'G5', 'no e2e harness yet')).toBe('SKIP G5 no e2e harness yet');
  });
});

describe('the --phase device matrix', () => {
  /** Every `name:` in the Playwright config's `projects` array, in order. */
  const configuredProjects = () => {
    const config = readFileSync(new URL('../../playwright.config.ts', import.meta.url), 'utf8');
    const projects = config.slice(config.indexOf('  projects: ['), config.indexOf('  webServer: ['));
    return [...projects.matchAll(/^\s+name: '([^']+)'/gm)].map((match) => match[1]);
  };

  it('runs every project the config declares', () => {
    // A `--phase` run that quietly skipped a project would report a green matrix
    // for a matrix it never ran. `chromium-motion` is the one this caught: it is
    // the only project with animations on, so without it the phase run proved
    // nothing about the @motion specs.
    expect(PHASE_PLAYWRIGHT_PROJECTS).toEqual(
      configuredProjects().map((name) => `--project=${name}`),
    );
  });

  it('includes the motion project', () => {
    expect(PHASE_PLAYWRIGHT_PROJECTS).toContain('--project=chromium-motion');
  });
});
