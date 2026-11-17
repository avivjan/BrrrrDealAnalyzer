// @vitest-environment jsdom
import { DOMWrapper, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import MoveToBoughtDialog from './MoveToBoughtDialog.vue'

let wrapper: VueWrapper | null = null
const at = (testid: string) => new DOMWrapper(document.querySelector(`[data-testid="${testid}"]`) as HTMLElement)
const exists = (testid: string) => document.querySelector(`[data-testid="${testid}"]`) !== null

function openTheDialog(initialGoogleDriveLink: string | null) {
  wrapper = mount(MoveToBoughtDialog, {
    props: { open: true, dealAddress: '12 Oak St', initialGoogleDriveLink, isMoving: false, serverErrorMessage: null },
    attachTo: document.body,
  })
  return wrapper
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

describe('Move to Bought asks for the deal\'s Google Drive folder', () => {
  it('prefills the deal\'s link and moves with it', async () => {
    const dialog = openTheDialog('https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOp')
    expect((at('move-to-bought.google-drive-link').element as HTMLInputElement).value).toBe('https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOp')
    await at('move-to-bought.confirm').trigger('click')
    expect(dialog.emitted('confirm')).toEqual([['https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOp']])
  })

  it('refuses an empty field and a link that is not a Drive folder, saying why', async () => {
    const dialog = openTheDialog(null)
    await at('move-to-bought.confirm').trigger('click')
    expect(dialog.emitted('confirm')).toBeUndefined()
    expect(at('move-to-bought.link-problem').text()).toContain('Paste')

    await at('move-to-bought.google-drive-link').setValue('https://docs.google.com/document/d/1AbCdEfGhIjKlMnOp/edit')
    await at('move-to-bought.confirm').trigger('click')
    expect(dialog.emitted('confirm')).toBeUndefined()
    expect(at('move-to-bought.link-problem').text()).toContain('not a Google Drive folder link')
    expect(exists('move-to-bought.error')).toBe(false)
  })
})
