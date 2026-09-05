import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
  E2E_FROZEN_PATHS,
  G1_PATHSPEC,
  G2_FROZEN_PATHS,
  GOLDEN_POLICY_PATHS,
  PHASE_PLAYWRIGHT_PROJECTS,
  e2eFreezeChecks,
  findGoldenPolicyViolations,
  gateLine,
  goldenPolicyGate,
} from './verify-ui.mjs';

describe('verify:ui pathspecs', () => {
  it('excludes the frontend, docs and scratch trees from G1', () => {
    expect(G1_PATHSPEC).toEqual([
      '.',
      ':!frontend',
      ':!docs',
      ':!design-system',
      ':!.superpowers',
      ':!**/__pycache__/**',
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
    });
    expect(gate.status).toBe('PASS');
  });

  it('fails and names the offending commit', () => {
    const gate = goldenPolicyGate({ tagExists: () => true, gitLog: () => log });
    expect(gate.status).toBe('FAIL');
    expect(gate.detail).toContain('bbb2222');
  });

  it('queries only the golden and allowlist paths of the ui-p0..HEAD range', () => {
    const calls = [];
    goldenPolicyGate({
      tagExists: () => true,
      gitLog: (range, paths) => {
        calls.push({ range, paths });
        return '';
      },
    });
    expect(calls).toEqual([{ range: 'ui-p0..HEAD', paths: GOLDEN_POLICY_PATHS }]);
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
