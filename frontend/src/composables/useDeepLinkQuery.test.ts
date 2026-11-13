// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { createMemoryHistory, createRouter, type LocationQuery } from 'vue-router'

import { NOT_HERE_ANY_MORE_MESSAGE, useDeepLinkQuery } from './useDeepLinkQuery'

const readOpenDeal = (query: LocationQuery) => (typeof query.openDeal === 'string' ? query.openDeal : null)

async function mountPageAt(url: string, actAnswersFound: boolean, startsReady = true) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:anything(.*)*', component: { render: () => null } }] })
  await router.push(url)
  await router.isReady()
  const act = vi.fn(async () => actAnswersFound)
  const isReady = ref(startsReady)
  const notFound = ref<string | null>(null)
  const Page = defineComponent({
    setup() {
      const { notFoundMessage } = useDeepLinkQuery(readOpenDeal, act, isReady)
      return () => { notFound.value = notFoundMessage.value; return h('div') }
    },
  })
  const wrapper = mount(Page, { global: { plugins: [router] } })
  await flushPromises()
  return { router, act, isReady, notFound, wrapper }
}

let unmount: (() => void) | null = null
afterEach(() => { unmount?.(); unmount = null })

describe('useDeepLinkQuery', () => {
  it('acts once on the link, then clears the query so a refresh does not act again', async () => {
    const page = await mountPageAt('/my-deals?openDeal=deal-1', true)
    unmount = () => page.wrapper.unmount()
    expect(page.act).toHaveBeenCalledTimes(1)
    expect(page.act).toHaveBeenCalledWith('deal-1')
    expect(page.router.currentRoute.value.fullPath).toBe('/my-deals')
    expect(page.notFound.value).toBeNull()
  })

  it('waits until the page data is ready', async () => {
    const page = await mountPageAt('/my-deals?openDeal=deal-1', true, false)
    unmount = () => page.wrapper.unmount()
    expect(page.act).not.toHaveBeenCalled()
    page.isReady.value = true
    await flushPromises()
    expect(page.act).toHaveBeenCalledTimes(1)
  })

  it('says the deal is no longer here when it is not found', async () => {
    const page = await mountPageAt('/my-deals?openDeal=deleted-deal', false)
    unmount = () => page.wrapper.unmount()
    expect(page.notFound.value).toBe(NOT_HERE_ANY_MORE_MESSAGE)
    expect(page.router.currentRoute.value.fullPath).toBe('/my-deals')
  })

  it('does nothing without a link, and acts on a new link while the page stays open', async () => {
    const page = await mountPageAt('/my-deals', true)
    unmount = () => page.wrapper.unmount()
    expect(page.act).not.toHaveBeenCalled()
    await page.router.push('/my-deals?openDeal=deal-2')
    await flushPromises()
    expect(page.act).toHaveBeenCalledWith('deal-2')
  })
})
