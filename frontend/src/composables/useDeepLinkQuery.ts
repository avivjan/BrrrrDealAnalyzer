/**
 * A page that a link can open on something (a deal, a row, a section): read the link's query once the page's data is
 * there, act on it, then clear it with `router.replace`, so a refresh does not act again and Back returns to the page
 * the link came from (tasks/todo/ConstructionAccountPerRehab.md, Step C0). The pattern My Deals already used.
 */
import { ref, watch, type Ref } from 'vue'
import { useRoute, useRouter, type LocationQuery } from 'vue-router'

export const NOT_HERE_ANY_MORE_MESSAGE = 'That deal is no longer here.'

/**
 * `read` turns the query into what to do (null = nothing for this page). `act` does it and answers false when the
 * thing is not found; the page then shows `notFoundMessage`. Runs when `isReady` becomes true, once per link.
 */
export function useDeepLinkQuery<T>(read: (query: LocationQuery) => T | null, act: (link: T) => boolean | Promise<boolean>,
  isReady: Ref<boolean>): { notFoundMessage: Ref<string | null> } {
  const route = useRoute()
  const router = useRouter()
  const notFoundMessage = ref<string | null>(null)
  let lastHandledFullPath: string | null = null

  async function handle(): Promise<void> {
    if (!isReady.value || route.fullPath === lastHandledFullPath) return
    const link = read(route.query)
    if (!link) return
    lastHandledFullPath = route.fullPath
    const found = await act(link)
    notFoundMessage.value = found ? null : NOT_HERE_ANY_MORE_MESSAGE
    await router.replace({ path: route.path, query: {}, hash: route.hash })
  }

  watch([isReady, () => route.fullPath], () => { void handle() }, { immediate: true })
  return { notFoundMessage }
}
