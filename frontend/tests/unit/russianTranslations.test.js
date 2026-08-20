import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const csv = readFileSync(
  resolve(process.cwd(), '../crm/translations/ru.csv'),
  'utf8',
)
const po = readFileSync(resolve(process.cwd(), '../crm/locale/ru.po'), 'utf8')

const expectedTranslations = {
  Paid: 'Оплачено',
  'Partially Paid': 'Частично оплачено',
  Unpaid: 'Не оплачено',
  Postpaid: 'Постоплата',
  Refunded: 'Возврат',
  Cancelled: 'Отменено',
  'Not specified': 'Не указан',
  Deal: 'Заказ',
  Deals: 'Заказы',
  'Create Deal': 'Создать заказ',
  'Convert to Deal': 'Преобразовать в заказ',
  'Open Deal': 'Открыть заказ',
  'Ongoing Deals': 'Текущие заказы',
  'Won Deals': 'Выполненные заказы',
  'Deal Owner': 'Ответственный за заказ',
  'Deal Value': 'Стоимость заказа',
}

const existingSelectTranslations = {
  New: 'Новый',
  Contacted: 'Связались',
  Qualified: 'Квалифицирован',
  Ready: 'Готов',
  Completed: 'Завершено',
  Prepayment: 'Предоплата',
  Postpayment: 'Постоплата',
  Cash: 'Наличные',
  'Bank Card': 'Банковская карта',
  'Bank Transfer': 'Банковский перевод',
  'Online Payment': 'Онлайн-оплата',
}

function parseCsv(input) {
  const rows = []
  let row = []
  let value = ''
  let quoted = false

  for (let index = 0; index < input.length; index += 1) {
    const char = input[index]
    if (char === '"') {
      if (quoted && input[index + 1] === '"') {
        value += '"'
        index += 1
      } else {
        quoted = !quoted
      }
    } else if (char === ',' && !quoted) {
      row.push(value)
      value = ''
    } else if ((char === '\n' || char === '\r') && !quoted) {
      if (char === '\r' && input[index + 1] === '\n') index += 1
      row.push(value)
      if (row.some((cell) => cell !== '')) rows.push(row)
      row = []
      value = ''
    } else {
      value += char
    }
  }
  if (value || row.length) {
    row.push(value)
    rows.push(row)
  }
  return new Map(rows.map(([source, translation]) => [source, translation]))
}

function parsePo(input) {
  const entries = new Map()
  let currentKey = null
  let msgid = ''
  let msgstr = ''

  function flush() {
    if (msgid) entries.set(msgid, msgstr)
    currentKey = null
    msgid = ''
    msgstr = ''
  }

  for (const line of `${input}\n`.split(/\r?\n/)) {
    if (!line.trim()) {
      flush()
    } else if (line.startsWith('msgid ')) {
      currentKey = 'msgid'
      msgid = JSON.parse(line.slice(6))
    } else if (line.startsWith('msgstr ')) {
      currentKey = 'msgstr'
      msgstr = JSON.parse(line.slice(7))
    } else if (line.startsWith('"') && currentKey) {
      const continuation = JSON.parse(line)
      if (currentKey === 'msgid') msgid += continuation
      if (currentKey === 'msgstr') msgstr += continuation
    }
  }
  return entries
}

const csvEntries = parseCsv(csv)
const poEntries = parsePo(po)

describe('Russian UI terminology catalogs', () => {
  it.each(Object.entries(expectedTranslations))(
    'keeps the exact %s entry synchronized in CSV and PO',
    (source, translation) => {
      expect(csvEntries.has(source)).toBe(true)
      expect(poEntries.has(source)).toBe(true)
      expect(csvEntries.get(source)).toBe(translation)
      expect(poEntries.get(source)).toBe(translation)
    },
  )

  it('does not retain user-facing Russian Deal terminology', () => {
    expect(csv).not.toMatch(/[Сс]делк/)
    expect(po).not.toMatch(/[Сс]делк/)
  })

  it.each(Object.entries(existingSelectTranslations))(
    'reuses the existing %s translation without a frontend lookup table',
    (source, translation) => {
      expect(csvEntries.get(source) || poEntries.get(source)).toBe(translation)
    },
  )

  it.each([
    'src/components/Layouts/AppSidebar.vue',
    'src/components/Mobile/MobileSidebar.vue',
  ])(
    'keeps raw Deals routing and translates only the %s menu label',
    (file) => {
      const source = readFileSync(resolve(process.cwd(), file), 'utf8')
      expect(source).toMatch(/label:\s*['"]Deals['"]/)
      expect(source).toMatch(/to:\s*['"]Deals['"]/)
      expect(source).toContain(':label="__(link.label)"')
    },
  )
})
