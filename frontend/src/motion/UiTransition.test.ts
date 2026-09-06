// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { h } from 'vue';
import { mount } from '@vue/test-utils';

import UiTransition from './UiTransition.vue';
import UiTransitionGroup from './UiTransitionGroup.vue';
import { presets } from './presets';

/**
 * The two wrappers are the *only* way Phase 4 reaches a view: the script freeze
 * means a template may write `<UiTransition preset="modal">` and nothing else.
 * So what matters here is the vnode they hand to Vue's built-in `<Transition>`
 * — the hooks that are on it, and the one prop that must never be.
 *
 * `mode` is the dangerous one. `mode="out-in"` holds the entering element back
 * until the leaving one is gone, which turns a decorative fade into a delay in
 * front of real content; the ban is a Phase 4 hard constraint, so it is checked
 * for every preset rather than for a sample.
 */

/**
 * Vue Test Utils stubs `<transition>` and `<transition-group>` by default,
 * which would replace exactly the thing under test; every mount here opts back
 * in to the real ones.
 */
const real = { global: { stubs: { transition: false, 'transition-group': false } } };

/** Props of the vnode a wrapper renders — the built-in `<Transition>` vnode. */
function rootProps(vm: unknown): Record<string, unknown> {
  const instance = vm as { $: { subTree: { props: Record<string, unknown> | null } } };
  return instance.$.subTree.props ?? {};
}

const presetNames = Object.keys(presets) as (keyof typeof presets)[];

describe('UiTransition', () => {
  it('renders its slot', () => {
    const wrapper = mount(UiTransition, {
      props: { preset: 'fade' as const },
      slots: { default: '<p class="child">content</p>' },
      ...real,
    });
    expect(wrapper.find('p.child').text()).toBe('content');
  });

  it('drives the transition from JavaScript, never from CSS classes', () => {
    const wrapper = mount(UiTransition, {
      props: { preset: 'fade' as const },
      slots: { default: '<p>content</p>' },
      ...real,
    });
    expect(rootProps(wrapper.vm).css).toBe(false);
  });

  it('passes appear through, so a first render can animate too', () => {
    const wrapper = mount(UiTransition, {
      props: { preset: 'fade' as const, appear: true },
      slots: { default: '<p>content</p>' },
      ...real,
    });
    expect(rootProps(wrapper.vm).appear).toBe(true);
  });

  it('does not appear by default', () => {
    const wrapper = mount(UiTransition, {
      props: { preset: 'fade' as const },
      slots: { default: '<p>content</p>' },
      ...real,
    });
    expect(rootProps(wrapper.vm).appear).toBe(false);
  });

  it('registers a leave hook only for a preset that animates out', () => {
    const withLeave = mount(UiTransition, {
      props: { preset: 'modal' as const },
      slots: { default: '<p>content</p>' },
      ...real,
    });
    expect(rootProps(withLeave.vm)).toHaveProperty('onLeave');
    expect(rootProps(withLeave.vm)).toHaveProperty('onLeaveCancelled');

    const enterOnly = mount(UiTransition, {
      props: { preset: 'page' as const },
      slots: { default: '<p>content</p>' },
      ...real,
    });
    expect(rootProps(enterOnly.vm)).not.toHaveProperty('onLeave');
    expect(rootProps(enterOnly.vm)).not.toHaveProperty('onLeaveCancelled');
    expect(rootProps(enterOnly.vm)).toHaveProperty('onEnter');
    expect(rootProps(enterOnly.vm)).toHaveProperty('onEnterCancelled');
  });

  it.each(presetNames)('never sets a mode (%s)', (preset) => {
    const wrapper = mount(UiTransition, {
      props: { preset },
      slots: { default: '<p>content</p>' },
      ...real,
    });
    expect(rootProps(wrapper.vm).mode).toBeUndefined();
  });
});

describe('UiTransitionGroup', () => {
  const items = () => [h('li', { key: 'a' }, 'a'), h('li', { key: 'b' }, 'b')];

  it('renders a div around the slot by default', () => {
    const wrapper = mount(UiTransitionGroup, {
      props: { preset: 'listItem' as const },
      slots: { default: items },
      ...real,
    });
    expect(wrapper.element.tagName).toBe('DIV');
    expect(wrapper.findAll('li')).toHaveLength(2);
  });

  it('renders the tag it is given', () => {
    const wrapper = mount(UiTransitionGroup, {
      props: { preset: 'listItem' as const, tag: 'ul' },
      slots: { default: items },
      ...real,
    });
    expect(wrapper.element.tagName).toBe('UL');
  });

  it('hands reordering to the ui-move class the stylesheet defines', () => {
    const wrapper = mount(UiTransitionGroup, {
      props: { preset: 'listItem' as const },
      slots: { default: items },
      ...real,
    });
    const props = rootProps(wrapper.vm);
    expect(props['move-class'] ?? props.moveClass).toBe('ui-move');
  });

  it.each(presetNames)('never sets a mode (%s)', (preset) => {
    const wrapper = mount(UiTransitionGroup, {
      props: { preset },
      slots: { default: items },
      ...real,
    });
    expect(rootProps(wrapper.vm).mode).toBeUndefined();
  });
});
