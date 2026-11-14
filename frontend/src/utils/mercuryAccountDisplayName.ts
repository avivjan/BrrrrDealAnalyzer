/**
 * A Mercury account as people read it: its name and the last four digits of its number, once.
 * Mercury's own account names often already end with those digits ("Mercury Checking ••8027"), so the digits are
 * added only when the name doesn't end with them.
 */
export interface MercuryAccountNameAndLastFour {
  name: string
  account_number_last_four?: string | null
}

export function mercuryAccountDisplayName(account: MercuryAccountNameAndLastFour | null | undefined): string {
  if (!account) return ''
  const accountName = (account.name ?? '').trim()
  const accountNumberLastFour = (account.account_number_last_four ?? '').trim()
  if (!accountNumberLastFour) return accountName
  const nameAlreadyEndsWithTheLastFour = new RegExp(`(^|[^0-9])${accountNumberLastFour}$`).test(accountName)
  return nameAlreadyEndsWithTheLastFour ? accountName : `${accountName} ••${accountNumberLastFour}`.trim()
}
