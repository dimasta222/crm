import {
  processField,
  translatePaymentStatusOptions,
  translatePaymentStatusValue,
  translateSelectOptions,
  translateSelectValue,
} from '@/utils/fieldTransforms'

const paymentStatuses = [
  'Paid',
  'Partially Paid',
  'Unpaid',
  'Postpaid',
  'Refunded',
  'Cancelled',
]

const otherSelectValues = [
  'New',
  'Contacted',
  'Qualified',
  'In Progress',
  'Ready',
  'Completed',
  'Prepayment',
  'Postpayment',
  'Cash',
  'Bank Card',
  'Bank Transfer',
  'Online Payment',
]

const expectedRussianPaymentOptions = [
  { label: 'Оплачено', value: 'Paid' },
  { label: 'Частично оплачено', value: 'Partially Paid' },
  { label: 'Не оплачено', value: 'Unpaid' },
  { label: 'Постоплата', value: 'Postpaid' },
  { label: 'Возврат', value: 'Refunded' },
  { label: 'Отменено', value: 'Cancelled' },
]

function translateRussianPaymentStatus(message) {
  const translations = {
    Paid: 'Оплачено',
    'Partially Paid': 'Частично оплачено',
    Unpaid: 'Не оплачено',
    Postpaid: 'Постоплата',
    Refunded: 'Возврат',
    Cancelled: 'Отменено',
    'Not specified': 'Не указан',
    Deal: 'Заказ',
    New: 'Новый',
    Contacted: 'Связались',
    Qualified: 'Квалифицирован',
    'In Progress': 'В работе',
    Ready: 'Готов',
    Completed: 'Завершено',
    Prepayment: 'Предоплата',
    Postpayment: 'Постоплата',
    Cash: 'Наличные',
    'Bank Card': 'Банковская карта',
    'Bank Transfer': 'Банковский перевод',
    'Online Payment': 'Онлайн-оплата',
  }
  return translations[message] || message
}

describe('payment status display in Russian', () => {
  const originalTranslate = globalThis.__
  const originalLanguage = globalThis.window.lang

  beforeEach(() => {
    globalThis.window.lang = 'ru'
    globalThis.__ = translateRussianPaymentStatus
  })

  afterEach(() => {
    globalThis.__ = originalTranslate
    if (originalLanguage === undefined) {
      delete globalThis.window.lang
    } else {
      globalThis.window.lang = originalLanguage
    }
  })

  it('localizes all stored payment status values without changing them', () => {
    const field = processField({
      fieldname: 'payment_status',
      fieldtype: 'Select',
      options: paymentStatuses.join('\n'),
      reqd: 1,
    })

    expect(field.options).toEqual(expectedRussianPaymentOptions)
  })

  it('localizes a missing payment status as Not specified', () => {
    for (const value of [null, undefined, '', '   ']) {
      expect(
        translateSelectValue(value, 'payment_status', 'Not specified'),
      ).toBe('Не указан')
    }
  })

  it('translates an arbitrary Select label but leaves its raw value intact', () => {
    const customSelect = processField({
      fieldname: 'custom_category',
      fieldtype: 'Select',
      options: 'Deal',
      reqd: 1,
    })
    const link = processField({
      fieldname: 'linked_document',
      fieldtype: 'Link',
      options: 'Deal',
    })

    expect(customSelect.options).toEqual([{ label: 'Заказ', value: 'Deal' }])
    expect(translateSelectValue('Deal', 'custom_category')).toBe('Заказ')
    expect(link.options).toBe('Deal')
  })

  it.each([
    ['lead statuses', ['New', 'Contacted', 'Qualified']],
    ['order statuses', ['In Progress', 'Ready', 'Completed']],
    ['payment terms', ['Prepayment', 'Postpayment']],
    [
      'payment methods',
      ['Cash', 'Bank Card', 'Bank Transfer', 'Online Payment'],
    ],
  ])('translates %s for display and preserves every raw value', (_, values) => {
    const options = translateSelectOptions(values, 'any_select_field')
    expect(options.map((option) => option.label)).toEqual(
      values.map(translateRussianPaymentStatus),
    )
    expect(options.map((option) => option.value)).toEqual(values)
  })

  it('builds translated filter labels while preserving raw values', () => {
    const options = translatePaymentStatusOptions(
      paymentStatuses,
      'payment_status',
    )
    expect(options).toEqual(expectedRussianPaymentOptions)
    expect(options.map((option) => option.value)).toEqual(paymentStatuses)
  })

  it('translates arbitrary Select labels in shared display paths', () => {
    expect(translatePaymentStatusOptions(['Deal'], 'custom_category')).toEqual([
      { label: 'Заказ', value: 'Deal' },
    ])
    expect(
      translatePaymentStatusValue('Deal', 'custom_category', 'Not specified'),
    ).toBe('Заказ')
  })
})

describe('payment status display in English', () => {
  const originalTranslate = globalThis.__
  const originalLanguage = globalThis.window.lang

  beforeEach(() => {
    globalThis.window.lang = 'en'
    globalThis.__ = (message) => message
  })

  afterEach(() => {
    globalThis.__ = originalTranslate
    if (originalLanguage === undefined) {
      delete globalThis.window.lang
    } else {
      globalThis.window.lang = originalLanguage
    }
  })

  it('shows all raw English Select labels and values', () => {
    const values = [...paymentStatuses, ...otherSelectValues]
    expect(translateSelectOptions(values, 'any_select_field')).toEqual(
      values.map((value) => ({ label: value, value })),
    )
    expect(translateSelectValue(null, 'payment_status', 'Not specified')).toBe(
      'Not specified',
    )
  })
})

describe('processField', () => {
  // ─── Cloning ──────────────────────────────────────────────────

  it('returns a new object, not the original', () => {
    const raw = { fieldname: 'status', fieldtype: 'Data', label: 'Status' }
    const result = processField(raw)
    expect(result).not.toBe(raw)
  })

  it('does not mutate the original field', () => {
    const raw = {
      fieldname: 'status',
      fieldtype: 'Select',
      options: 'New\nOpen',
    }
    processField(raw)
    expect(raw.options).toBe('New\nOpen')
    expect(raw.fieldtype).toBe('Select')
  })

  it('does not mutate the original when overrides are applied', () => {
    const raw = { fieldname: 'x', fieldtype: 'Data', label: 'Original' }
    processField(raw, { propertyOverrides: { x: { label: 'Changed' } } })
    expect(raw.label).toBe('Original')
  })

  it('returns null for null input', () => {
    expect(processField(null)).toBeNull()
  })

  it('returns null for undefined input', () => {
    expect(processField(undefined)).toBeNull()
  })

  // ─── Select option transform ──────────────────────────────────

  it('converts Select options string to {label,value} array', () => {
    const raw = {
      fieldname: 'status',
      fieldtype: 'Select',
      options: 'New\nOpen\nClosed',
    }
    const result = processField(raw)
    expect(result.options).toEqual([
      { label: '', value: '' },
      { label: 'New', value: 'New' },
      { label: 'Open', value: 'Open' },
      { label: 'Closed', value: 'Closed' },
    ])
  })

  it('prepends blank option for non-required Select', () => {
    const raw = {
      fieldname: 'priority',
      fieldtype: 'Select',
      options: 'Low\nHigh',
    }
    const result = processField(raw)
    expect(result.options[0]).toEqual({ label: '', value: '' })
    expect(result.options).toHaveLength(3)
  })

  it('skips blank option for required Select', () => {
    const raw = {
      fieldname: 'status',
      fieldtype: 'Select',
      options: 'New\nOpen',
      reqd: 1,
    }
    const result = processField(raw)
    expect(result.options[0]).toEqual({ label: 'New', value: 'New' })
    expect(result.options).toHaveLength(2)
  })

  it('does not prepend blank when first option is already blank', () => {
    const raw = { fieldname: 'x', fieldtype: 'Select', options: '\nA\nB' }
    const result = processField(raw)
    expect(result.options[0]).toEqual({ label: '', value: '' })
    // should NOT have two blanks
    expect(result.options.filter((o) => o.value === '')).toHaveLength(1)
  })

  it('handles single option Select', () => {
    const raw = { fieldname: 'x', fieldtype: 'Select', options: 'Only' }
    const result = processField(raw)
    expect(result.options).toEqual([
      { label: '', value: '' },
      { label: 'Only', value: 'Only' },
    ])
  })

  it('handles empty options string', () => {
    const raw = { fieldname: 'x', fieldtype: 'Select', options: '' }
    const result = processField(raw)
    // '' split by \n gives [''] — first value is '' so no blank prepended
    expect(result.options).toEqual([{ label: '', value: '' }])
  })

  it('does not transform if options is already an array', () => {
    const opts = [{ label: 'A', value: 'A' }]
    const raw = { fieldname: 'x', fieldtype: 'Select', options: opts }
    const result = processField(raw)
    expect(result.options).toEqual(opts)
  })

  it('does not transform options for non-Select field types', () => {
    const raw = { fieldname: 'x', fieldtype: 'Data', options: 'Email' }
    const result = processField(raw)
    expect(result.options).toBe('Email')
  })

  // ─── Link→User transform ─────────────────────────────────────

  it('transforms Link with options=User to fieldtype User', () => {
    const raw = { fieldname: 'owner', fieldtype: 'Link', options: 'User' }
    const result = processField(raw)
    expect(result.fieldtype).toBe('User')
    // original untouched
    expect(raw.fieldtype).toBe('Link')
  })

  it('does not transform Link with other options', () => {
    const raw = { fieldname: 'org', fieldtype: 'Link', options: 'Organization' }
    const result = processField(raw)
    expect(result.fieldtype).toBe('Link')
    expect(result.options).toBe('Organization')
  })

  it('does not transform non-Link field types', () => {
    const raw = { fieldname: 'x', fieldtype: 'Data', options: 'User' }
    const result = processField(raw)
    expect(result.fieldtype).toBe('Data')
  })

  // ─── Perm overrides ──────────────────────────────────────────

  it('applies perm overrides', () => {
    const raw = { fieldname: 'salary', fieldtype: 'Currency', read_only: 0 }
    const result = processField(raw, {
      permOverrides: { salary: { read_only: 1 } },
    })
    expect(result.read_only).toBe(1)
  })

  it('perm overrides do not mutate original', () => {
    const raw = { fieldname: 'salary', fieldtype: 'Currency', read_only: 0 }
    processField(raw, { permOverrides: { salary: { read_only: 1 } } })
    expect(raw.read_only).toBe(0)
  })

  // ─── Script property overrides ────────────────────────────────

  it('applies script property overrides', () => {
    const raw = {
      fieldname: 'email',
      fieldtype: 'Data',
      hidden: 0,
      label: 'Email',
    }
    const result = processField(raw, {
      propertyOverrides: { email: { hidden: 1, label: 'Work Email' } },
    })
    expect(result.hidden).toBe(1)
    expect(result.label).toBe('Work Email')
  })

  it('script overrides win over perm overrides', () => {
    const raw = { fieldname: 'salary', fieldtype: 'Currency', read_only: 0 }
    const result = processField(raw, {
      permOverrides: { salary: { read_only: 1 } },
      propertyOverrides: { salary: { read_only: 0 } },
    })
    expect(result.read_only).toBe(0)
  })

  it('script overrides win over raw field values', () => {
    const raw = { fieldname: 'x', fieldtype: 'Data', label: 'Old', hidden: 0 }
    const result = processField(raw, {
      propertyOverrides: { x: { label: 'New', hidden: true } },
    })
    expect(result.label).toBe('New')
    expect(result.hidden).toBe(true)
  })

  it('unrelated overrides do not affect the field', () => {
    const raw = { fieldname: 'email', fieldtype: 'Data', label: 'Email' }
    const result = processField(raw, {
      propertyOverrides: { other_field: { hidden: true } },
    })
    expect(result.label).toBe('Email')
    expect(result.hidden).toBeUndefined()
  })

  // ─── Override changes Select options ──────────────────────────

  it('override can replace Select options string', () => {
    const raw = { fieldname: 'status', fieldtype: 'Select', options: 'A\nB' }
    const result = processField(raw, {
      propertyOverrides: { status: { options: 'X\nY\nZ' } },
    })
    expect(result.options).toEqual([
      { label: '', value: '' },
      { label: 'X', value: 'X' },
      { label: 'Y', value: 'Y' },
      { label: 'Z', value: 'Z' },
    ])
  })

  it('override reqd affects blank option prepending', () => {
    const raw = {
      fieldname: 'status',
      fieldtype: 'Select',
      options: 'A\nB',
      reqd: 0,
    }
    const result = processField(raw, {
      propertyOverrides: { status: { reqd: 1 } },
    })
    // reqd=1 from override → no blank option
    expect(result.options[0]).toEqual({ label: 'A', value: 'A' })
  })

  // ─── Combined transforms ─────────────────────────────────────

  it('applies overrides before Select transform', () => {
    // Override changes options string, then transform converts to array
    const raw = { fieldname: 's', fieldtype: 'Select', options: 'Old1\nOld2' }
    const result = processField(raw, {
      propertyOverrides: { s: { options: 'New1\nNew2\nNew3' } },
    })
    expect(result.options).toHaveLength(4) // blank + 3
    expect(result.options[1].value).toBe('New1')
  })

  it('preserves non-overridden properties', () => {
    const raw = {
      fieldname: 'x',
      fieldtype: 'Data',
      label: 'X',
      description: 'Help text',
      placeholder: 'Enter X',
    }
    const result = processField(raw, {
      propertyOverrides: { x: { label: 'Y' } },
    })
    expect(result.label).toBe('Y')
    expect(result.description).toBe('Help text')
    expect(result.placeholder).toBe('Enter X')
  })
})
