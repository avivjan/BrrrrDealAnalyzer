#!/usr/bin/env node
/**
 * `npm run verify:ui` — the whole behaviour-freeze gate set, in order.
 *
 * Run from `frontend/`. Prints exactly one `PASS|FAIL|SKIP <gate> <detail>`
 * line per gate (with each gate's own problem lines indented above it) and
 * exits 1 when any gate fails.
 *
 *   --phase   additionally run the backend regression proofs and, once the
 *             harness exists, the full Playwright device matrix.
 */
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { FRONTEND_ROOT, REPO_ROOT, isCliEntry } from './sfc.mjs';
import { run as runScriptBlocks } from './script-blocks.mjs';
import { run as runBindings } from './bindings.mjs';
import { run as runText } from './text.mjs';
import { run as runHoverPairs, TOUCH_REVEAL } from './hover-pairs.mjs';

/** The baseline every non-frontend file is frozen against. */
export const BASELINE_TAG = 'ui-baseline';
/** The Phase 0 tag that additionally freezes the e2e suite and the goldens. */
export const PHASE_0_TAG = 'ui-p0';

/** G1: everything outside the frontend (and outside scratch dirs) is frozen. */
export const G1_PATHSPEC = [
  '.',
  ':!frontend',
  ':!docs',
  ':!design-system',
  ':!.superpowers',
  // Tracked .pyc files are rewritten by the backend proofs; never a real change.
  ':!**/__pycache__/**',
];

/** G2: frontend directories that hold behaviour rather than presentation. */
export const G2_FROZEN_PATHS = [
  'frontend/src/stores',
  'frontend/src/api',
  'frontend/src/utils',
  'frontend/src/router',
  'frontend/src/types',
  'frontend/src/config',
];

/** G2 (from ui-p0 on): the e2e suite itself is frozen. */
export const E2E_FROZEN_PATHS = ['frontend/e2e/flows', 'frontend/e2e/fixtures'];

/** Paths only a `Golden update:` commit may touch. */
export const GOLDEN_POLICY_PATHS = [
  'frontend/scripts/audit/golden',
  'frontend/e2e/golden',
  'frontend/scripts/audit/allowlist.json',
];

const PLAYWRIGHT_CONFIG = join(FRONTEND_ROOT, 'playwright.config.ts');
const PHASE_PLAYWRIGHT_PROJECTS = [
  '--project=chromium',
  '--project=webkit',
  '--project=Mobile Safari',
  '--project=Mobile Chrome',
];

export function gateLine(status, gate, detail) {
  return `${status} ${gate} ${detail}`;
}

// ---------------------------------------------------------------------------
// git helpers (all injectable so the gates are unit-testable without tags)
// ---------------------------------------------------------------------------

function git(args, cwd = REPO_ROOT) {
  return spawnSync('git', args, { cwd, encoding: 'utf8' });
}

export function gitTagExists(tag) {
  return git(['rev-parse', '--verify', '--quiet', `refs/tags/${tag}`]).status === 0;
}

export function gitLogSubjects(range, paths) {
  const result = git(['log', '--format=%h%x09%s', range, '--', ...paths]);
  return result.status === 0 ? result.stdout : '';
}

/** `git diff --quiet <ref> -- <paths>` — true when the tree still matches `ref`. */
export function isCleanAgainst(ref, paths) {
  return git(['diff', '--quiet', ref, '--', ...paths]).status === 0;
}

// ---------------------------------------------------------------------------
// ui-p0-conditional pieces (inert until the tag is cut)
// ---------------------------------------------------------------------------

/** The extra G2 diff checks that switch on once `ui-p0` exists. */
export function e2eFreezeChecks({ tagExists = gitTagExists, tag = PHASE_0_TAG } = {}) {
  return tagExists(tag) ? [{ ref: tag, paths: E2E_FROZEN_PATHS }] : [];
}

/** Commits in the log that touched a golden path without a `Golden update:` subject. */
export function findGoldenPolicyViolations(logOutput) {
  return logOutput
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const tab = line.indexOf('\t');
      return { sha: line.slice(0, tab), subject: line.slice(tab + 1) };
    })
    .filter((commit) => !commit.subject.startsWith('Golden update:'));
}

export function goldenPolicyGate({
  tagExists = gitTagExists,
  gitLog = gitLogSubjects,
  tag = PHASE_0_TAG,
} = {}) {
  if (!tagExists(tag)) {
    return { status: 'SKIP', detail: `no ${tag} tag yet` };
  }
  const range = `${tag}..HEAD`;
  const violations = findGoldenPolicyViolations(gitLog(range, GOLDEN_POLICY_PATHS));
  if (violations.length === 0) {
    return { status: 'PASS', detail: `every golden change in ${range} is a "Golden update:" commit` };
  }
  const named = violations.map((commit) => `${commit.sha} ${commit.subject}`).join('; ');
  return { status: 'FAIL', detail: `golden files changed outside a "Golden update:" commit: ${named}` };
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

function printGateResult(status, gate, detail, failures) {
  if (status === 'FAIL') failures.push(gate);
  console.log(gateLine(status, gate, detail));
}

/** Print an audit gate's own problem lines, then its verdict. */
function printAuditGate(gate, result, failures, okDetail = 'no behaviour drift') {
  for (const line of result.lines) console.log(`  ${line.level} ${line.text}`);
  printGateResult(result.ok ? 'PASS' : 'FAIL', gate, result.ok ? okDetail : 'see the lines above', failures);
}

function runCommand(command, args, cwd) {
  return spawnSync(command, args, { cwd, stdio: 'inherit', shell: false }).status === 0;
}

/** Undo the tracked `__pycache__` churn the backend proofs leave behind. */
function restorePycache() {
  const listed = git(['ls-files', '-m', '--', '**/__pycache__/**']);
  const files = (listed.stdout ?? '').split('\n').map((line) => line.trim()).filter(Boolean);
  if (files.length > 0) git(['restore', '--', ...files]);
  return files;
}

function main(argv) {
  const phase = argv.includes('--phase');
  const failures = [];

  const haveBaseline = gitTagExists(BASELINE_TAG);
  const missingBaseline = `baseline tag ${BASELINE_TAG} is missing`;

  // G1 — nothing outside the frontend has moved since the baseline.
  printGateResult(
    haveBaseline && isCleanAgainst(BASELINE_TAG, G1_PATHSPEC) ? 'PASS' : 'FAIL',
    'G1',
    haveBaseline ? `backend and root files unchanged since ${BASELINE_TAG}` : missingBaseline,
    failures,
  );

  // G2 — behavioural frontend directories (and, from ui-p0 on, the e2e suite).
  const g2Checks = haveBaseline
    ? [{ ref: BASELINE_TAG, paths: G2_FROZEN_PATHS }, ...e2eFreezeChecks()]
    : [];
  const dirty = g2Checks.filter((check) => !isCleanAgainst(check.ref, check.paths));
  printGateResult(
    haveBaseline && dirty.length === 0 ? 'PASS' : 'FAIL',
    'G2',
    !haveBaseline
      ? missingBaseline
      : dirty.length === 0
        ? `stores/api/utils/router/types/config unchanged since ${BASELINE_TAG}`
        : `changed since ${dirty.map((check) => check.ref).join(', ')}: ${dirty
            .flatMap((check) => check.paths)
            .join(' ')}`,
    failures,
  );

  printAuditGate('G3', runScriptBlocks(), failures);
  printAuditGate('G4', runBindings(), failures);
  printAuditGate('G4b', runText(), failures);

  // G-HOVER — with `hoverOnlyWhenSupported` on, a hover-only reveal is invisible
  // (but still clickable) on touch, which no Playwright or axe run can catch.
  const hover = runHoverPairs();
  printAuditGate('G-HOVER', hover, failures, `every hover reveal pairs with ${TOUCH_REVEAL}`);

  // G6 — the suite and the production build.
  const testsPass = runCommand('npm', ['test'], FRONTEND_ROOT);
  const buildPasses = testsPass && runCommand('npm', ['run', 'build'], FRONTEND_ROOT);
  printGateResult(
    testsPass && buildPasses ? 'PASS' : 'FAIL',
    'G6',
    testsPass && buildPasses ? 'npm test and npm run build both succeeded' : 'npm test or npm run build failed',
    failures,
  );

  // G5 / G7 — end-to-end flows and screenshots, once the harness lands.
  if (existsSync(PLAYWRIGHT_CONFIG)) {
    const projects = phase ? PHASE_PLAYWRIGHT_PROJECTS : [];
    const e2ePasses = runCommand('npx', ['playwright', 'test', ...projects], FRONTEND_ROOT);
    const detail = phase ? 'playwright, full device matrix' : 'playwright, default projects';
    printGateResult(e2ePasses ? 'PASS' : 'FAIL', 'G5', detail, failures);
    printGateResult(e2ePasses ? 'PASS' : 'FAIL', 'G7', detail, failures);
  } else {
    printGateResult('SKIP', 'G5', 'no e2e harness yet', failures);
    printGateResult('SKIP', 'G7', 'no e2e harness yet', failures);
  }

  const policy = goldenPolicyGate();
  printGateResult(policy.status, 'GOLDEN-POLICY', policy.detail, failures);

  if (phase) {
    const backendRoot = join(REPO_ROOT, 'BackEnd');
    const regressionPasses = runCommand('python3', ['verify_regression.py', 'verify'], backendRoot);
    const pytestPasses = runCommand('python3', ['-m', 'pytest', '-q'], backendRoot);
    const restored = restorePycache();
    printGateResult(
      regressionPasses && pytestPasses ? 'PASS' : 'FAIL',
      'BACKEND',
      `verify_regression.py + pytest${restored.length > 0 ? ` (restored ${restored.length} __pycache__ file(s))` : ''}`,
      failures,
    );
  }

  // Not a gate: the two files the reviewer reads by hand.
  console.log('');
  console.log('Reviewed diffs (main.ts, vite.config.ts):');
  const reviewed = git([
    'diff',
    '--stat',
    BASELINE_TAG,
    '--',
    'frontend/src/main.ts',
    'frontend/vite.config.ts',
  ]);
  process.stdout.write(reviewed.stdout || '  (no changes)\n');

  if (failures.length > 0) {
    console.log('');
    console.log(`verify:ui FAIL (${failures.join(', ')})`);
    process.exitCode = 1;
  } else {
    console.log('');
    console.log('verify:ui PASS');
  }
}

if (isCliEntry(import.meta.url)) {
  main(process.argv.slice(2));
}
