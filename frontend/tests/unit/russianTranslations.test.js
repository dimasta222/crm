import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

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
  'Order composition': 'Состав заказа',
  'Order type': 'Тип заказа',
  'Select order type': 'Выберите тип заказа',
  'Select option': 'Выберите значение',
  Items: 'Изделия',
  'Add item': 'Добавить изделие',
  Applications: 'Нанесения',
  'Add application': 'Добавить нанесение',
  'DTF Roll': 'DTF в рулоне',
  'Add roll': 'Добавить рулон',
  'DTF Pieces': 'DTF поштучно',
  'Add position': 'Добавить позицию',
  'Preliminary calculation': 'Предварительный расчёт',
  'Items cost': 'Стоимость изделий',
  'Applications cost': 'Стоимость услуг и нанесений',
  Subtotal: 'Промежуточный итог',
  'Order discount, %': 'Скидка на заказ, %',
  Discount: 'Скидка',
  Total: 'Итого',
  'Set amount manually': 'Указать сумму вручную',
  'Back placement': 'Спина',
  Back: 'Назад',
  'Combined order': 'Комбинированный',
  'The order retains rows from other types: {0}.':
    'В заказе сохранены строки других типов: {0}.',
  'This item has applications. Remove or reassign them before deleting the item.':
    'У изделия есть нанесения. Перед удалением удалите их или назначьте другому изделию.',
  'Name / Product': 'Название / изделие',
  Supply: 'Поставка',
  Qty: 'Кол-во',
  Rate: 'Цена',
  'Discount %': 'Скидка, %',
  'Item name': 'Название изделия',
  'Select CRM Product': 'Выберите изделие CRM',
  'Set rate manually': 'Указать цену вручную',
  'Delete row': 'Удалить строку',
  'No items added': 'Изделия не добавлены',
  'Customer Item': 'Изделие клиента',
  'Studio Product': 'Товар студии',
  'DTF Printing': 'DTF-печать',
  'Screen Printing': 'Шелкография',
  Embroidery: 'Вышивка',
  Sublimation: 'Сублимация',
  'Heat Transfer Printing': 'Термоперенос',
  Combined: 'Комбинированное нанесение',
  Chest: 'Грудь',
  Sleeve: 'Рукав',
  'Tag / Inner Part': 'Бирка / внутренняя часть',
  Other: 'Другое',
  Format: 'Формат',
  'Custom Size': 'Свой размер',
  'Quantity Only': 'Только количество',
  Manual: 'Вручную',
  'The selected product has no standard rate.':
    'У выбранного изделия не указана стандартная цена.',
  'Unable to load the product rate.': 'Не удалось загрузить цену изделия.',
  'Unable to create the product.': 'Не удалось создать изделие.',
  'Could not move the card. The change was not saved.':
    'Не удалось переместить карточку. Изменение не сохранено.',
  'Create product': 'Создать изделие',
  'Open product': 'Открыть изделие',
  'Width (cm)': 'Ширина, см',
  'Height (cm)': 'Высота, см',
  'Calculated amount': 'Расчётная сумма',
  'Manual amount': 'Ручная сумма',
  'Final amount': 'Итоговая сумма',
  'Equivalent rate per meter': 'Эквивалентная цена за метр',
  'Apply as rate per meter': 'Применить как цену за метр',
  Item: 'Изделие',
  'Production type': 'Тип производства',
  Placement: 'Расположение',
  'No applications added': 'Нанесения не добавлены',
  'Add an item before adding an application': 'Сначала добавьте изделие',
  'Rate per meter': 'Цена за метр',
  'No rolls added': 'Рулоны не добавлены',
  Sizing: 'Способ задания размера',
  'Unit price': 'Цена за единицу',
  'No positions added': 'Позиции не добавлены',
  'Order total': 'Итого по заказу',
  'Enter amount': 'Введите сумму',
  'DTF Roll cost': 'Стоимость DTF в рулоне',
  'DTF Pieces cost': 'Стоимость DTF поштучно',
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
const orderEditorFiles = [
  'OrderEditor.vue',
  'OrderItemsTable.vue',
  'OrderApplicationsTable.vue',
  'DtfRollTable.vue',
  'DtfPiecesTable.vue',
  'OrderTotalsPreview.vue',
]
const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const csvSourceRegExp = (source) =>
  new RegExp(
    source.includes(',')
      ? `^"${escapeRegExp(source)}",`
      : `^${escapeRegExp(source)},`,
    'gm',
  )

describe('Russian UI terminology catalogs', () => {
  it.each(Object.entries(expectedTranslations))(
    'keeps the exact %s entry synchronized in CSV and PO',
    (source, translation) => {
      expect(csvEntries.has(source)).toBe(true)
      expect(poEntries.has(source)).toBe(true)
      expect(csvEntries.get(source)).toBe(translation)
      expect(poEntries.get(source)).toBe(translation)
      expect(
        csv.match(csvSourceRegExp(source)) || [],
      ).toHaveLength(1)
      expect(
        po.match(new RegExp(`^msgid "${escapeRegExp(source)}"$`, 'gm')) || [],
      ).toHaveLength(1)
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

  it('localizes every literal OrderEditor message in both catalogs', () => {
    const messages = new Set()
    for (const file of orderEditorFiles) {
      const source = readFileSync(
        resolve(process.cwd(), 'src/components/OrderEditor', file),
        'utf8',
      )
      for (const match of source.matchAll(/__\(\s*(['"])(.*?)\1/gs)) {
        if (match[2] !== '—') messages.add(match[2])
      }
    }

    for (const message of messages) {
      expect(
        csvEntries.get(message),
        `${message} is missing in ru.csv`,
      ).toBeTruthy()
      expect(
        poEntries.get(message),
        `${message} is missing in ru.po`,
      ).toBeTruthy()
      expect(
        csv.match(csvSourceRegExp(message)) || [],
        `${message} is duplicated in ru.csv`,
      ).toHaveLength(1)
      expect(
        po.match(new RegExp(`^msgid "${escapeRegExp(message)}"$`, 'gm')) || [],
        `${message} is duplicated in ru.po`,
      ).toHaveLength(1)
    }
  })

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
