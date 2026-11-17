import { describe, expect, it } from 'vitest'

import { googleDriveFolderLinkProblem } from './googleDriveFolderLink'

describe('googleDriveFolderLinkProblem', () => {
  it('accepts a Drive folder link, with an account number or a share suffix', () => {
    expect(googleDriveFolderLinkProblem('https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOp')).toBeNull()
    expect(googleDriveFolderLinkProblem(' https://drive.google.com/drive/u/0/folders/1AbCdEfGhIjKlMnOp?usp=sharing ')).toBeNull()
  })

  it('explains an empty field, a file or doc link, another site and plain text', () => {
    expect(googleDriveFolderLinkProblem('')).toContain('Paste')
    for (const badLink of ['https://drive.google.com/file/d/1AbCdEfGhIjKlMnOp/view', 'https://docs.google.com/document/d/1AbCdEfGhIjKlMnOp/edit',
      'http://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOp', 'https://example.com/drive/folders/1AbCdEfGhIjKlMnOp']) {
      expect(googleDriveFolderLinkProblem(badLink)).toContain('not a Google Drive folder link')
    }
    expect(googleDriveFolderLinkProblem('my folder')).toContain('not a link')
  })
})
