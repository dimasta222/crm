// @vitest-environment happy-dom
/* eslint-disable vue/one-component-per-file, vue/require-prop-types */

import { createApp, defineComponent, h } from 'vue'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

vi.mock('frappe-ui', async () => {
  const { defineComponent, h } = await import('vue')
  const Button = defineComponent({
    props: ['label', 'tooltip'],
    emits: ['click'],
    setup:
      (props, { emit }) =>
      () =>
        h(
          'button',
          { title: props.tooltip, onClick: () => emit('click') },
          props.label || props.tooltip,
        ),
  })
  const Checkbox = defineComponent({
    props: ['modelValue', 'label'],
    emits: ['update:modelValue'],
    setup:
      (props, { emit }) =>
      () =>
        h('label', [
          h('input', {
            type: 'checkbox',
            checked: Boolean(props.modelValue),
            onChange: (event) =>
              emit('update:modelValue', event.target.checked),
          }),
          props.label,
        ]),
  })
  const FormControl = defineComponent({
    props: ['modelValue', 'label', 'placeholder', 'type'],
    emits: ['update:modelValue', 'input'],
    setup:
      (props, { emit }) =>
      () =>
        h('label', [
          props.label,
          h('input', {
            type: props.type || 'text',
            value: props.modelValue,
            placeholder: props.placeholder,
            onInput: (event) => {
              emit('update:modelValue', event.target.value)
              emit('input', event)
            },
          }),
        ]),
  })
  const Select = defineComponent({
    props: ['modelValue', 'options', 'placeholder'],
    emits: ['update:modelValue'],
    setup:
      (props, { emit }) =>
      () =>
        h(
          'select',
          {
            value: props.modelValue,
            'data-placeholder': props.placeholder,
            onChange: (event) => emit('update:modelValue', event.target.value),
          },
          [
            h('option', { disabled: true, value: '' }, props.placeholder),
            ...(props.options || []).map((option) =>
              h(
                'option',
                { value: option.value ?? option },
                option.label ?? option,
              ),
            ),
          ],
        ),
  })
  return {
    Button,
    Checkbox,
    FormControl,
    Select,
    createResource: () => ({ fetch: vi.fn() }),
  }
})

vi.mock('@/components/Section.vue', () => ({
  default: defineComponent({
    props: ['label'],
    setup:
      (props, { slots }) =>
      () =>
        h('section', [
          h('h3', props.label),
          slots.actions?.(),
          slots.default?.(),
        ]),
  }),
}))

vi.mock('@/components/Controls/Link.vue', () => ({
  default: defineComponent({
    props: ['modelValue', 'placeholder'],
    setup: (props) => () =>
      h('input', { value: props.modelValue, placeholder: props.placeholder }),
  }),
}))

vi.mock('@/stores/meta', () => ({
  getMeta: () => ({ doctypeMeta: { value: { fields: [] } } }),
}))

import OrderEditor from '@/components/OrderEditor/OrderEditor.vue'

const ru = {
  'Order composition': 'Состав заказа',
  'Order type': 'Тип заказа',
  'Select order type': 'Выберите тип заказа',
  'Select option': 'Выберите значение',
  'Product Printing': 'Печать на изделиях',
  'DTF Roll': 'DTF в рулоне',
  'DTF Pieces': 'DTF поштучно',
  'Combined order': 'Комбинированный',
  Items: 'Изделия',
  'Add item': 'Добавить изделие',
  Applications: 'Нанесения',
  'Add application': 'Добавить нанесение',
  'Services and applications': 'Услуги и нанесения',
  'Add service': 'Добавить услугу',
  'Add roll': 'Добавить рулон',
  'Add position': 'Добавить позицию',
  'Name / Product': 'Название / изделие',
  Supply: 'Поставка',
  Qty: 'Кол-во',
  Rate: 'Цена',
  'Discount %': 'Скидка, %',
  'Item name': 'Название изделия',
  'Select CRM Product': 'Выберите изделие CRM',
  'Set rate manually': 'Указать цену вручную',
  'Not charged': 'Не оплачивается',
  'Delete row': 'Удалить строку',
  'No items added': 'Изделия не добавлены',
  'Customer Item': 'Изделие клиента',
  'Studio Product': 'Товар студии',
  Item: 'Изделие',
  'Production type': 'Тип производства',
  Placement: 'Расположение',
  'No applications added': 'Нанесения не добавлены',
  'Add an item before adding an application': 'Сначала добавьте изделие',
  'DTF Printing': 'DTF-печать',
  'Screen Printing': 'Шелкография',
  Embroidery: 'Вышивка',
  Sublimation: 'Сублимация',
  'Heat Transfer Printing': 'Термоперенос',
  'Artwork Preparation': 'Подготовка и правка макета',
  Combined: 'Комбинированное нанесение',
  Parameters: 'Параметры',
  Chest: 'Грудь',
  'Back placement': 'Спина',
  Sleeve: 'Рукав',
  'Tag / Inner Part': 'Бирка / внутренняя часть',
  Other: 'Другое',
  'Length (m)': 'Длина (м)',
  'Rate per meter': 'Цена за метр',
  Amount: 'Сумма',
  Comment: 'Комментарий',
  'Set amount manually': 'Указать сумму вручную',
  'No rolls added': 'Рулоны не добавлены',
  Sizing: 'Способ задания размера',
  Size: 'Размер',
  'Unit price': 'Цена за единицу',
  'No positions added': 'Позиции не добавлены',
  Format: 'Формат',
  'Custom Size': 'Свой размер',
  'Quantity Only': 'Только количество',
  Width: 'Ширина',
  Height: 'Высота',
  'Unable to create the product.': 'Не удалось создать изделие.',
  'Create product': 'Создать изделие',
  'Open product': 'Открыть изделие',
  'Width (cm)': 'Ширина, см',
  'Height (cm)': 'Высота, см',
  'Calculated amount': 'Расчётная сумма',
  'Manual amount': 'Ручная сумма',
  'Final amount': 'Итоговая сумма',
  'Equivalent rate per meter': 'Эквивалентная цена за метр',
  'Apply as rate per meter': 'Применить как цену за метр',
  'Preliminary calculation': 'Предварительный расчёт',
  'Items cost': 'Стоимость изделий',
  'Applications cost': 'Стоимость услуг и нанесений',
  Discount: 'Скидка',
  Total: 'Итого',
  'DTF Roll cost': 'Стоимость DTF в рулоне',
  'DTF Pieces cost': 'Стоимость DTF поштучно',
  'Order total': 'Итого по заказу',
  'Enter amount': 'Введите сумму',
  '—': '—',
}

let mountedApp

function mountEditor(doc) {
  const container = document.createElement('div')
  document.body.append(container)
  mountedApp = createApp(OrderEditor, { doc })
  mountedApp.config.globalProperties.__ = globalThis.__
  mountedApp.mount(container)
  return container
}

function visibleSelectData(container) {
  return [...container.querySelectorAll('select')].map((select) => ({
    placeholder: select.dataset.placeholder,
    options: [...select.options].slice(1).map((option) => ({
      label: option.textContent,
      value: option.value,
    })),
  }))
}

function expectNoUserFacingEnglish(container) {
  const visible = [
    container.textContent,
    ...[...container.querySelectorAll('[placeholder], [title]')].flatMap(
      (element) => [element.getAttribute('placeholder'), element.title],
    ),
  ].join(' ')
  expect(visible).not.toMatch(
    /Select option|Customer Item|Studio Product|Screen Printing|Embroidery|Sublimation|Heat Transfer Printing|Combined|Chest|Back|Sleeve|Tag \/ Inner Part|Other|Custom Size|Quantity Only|Manual|Add |Delete |No items|No applications|No rolls|No positions|Order total/,
  )
  const unexpectedLatin = visible
    .replace(/DTF|CRM|RUB|USD|A6|A5|A4|A3\+\+|A3\+|A3/g, '')
    .match(/[A-Za-z]{2,}/g)
  expect([...new Set(unexpectedLatin || [])]).toEqual([])
}

beforeAll(() => {
  globalThis.__ = (message, replacements = []) =>
    (ru[message] || message).replace(
      /\{(\d+)\}/g,
      (_, index) => replacements[Number(index)] ?? '',
    )
  window.sysdefaults = { currency_precision: 2 }
})

afterEach(() => {
  mountedApp?.unmount()
  mountedApp = null
  document.body.replaceChildren()
})

describe('OrderEditor Russian component UI', () => {
  it('renders the empty editor without English placeholders or empty states', () => {
    const container = mountEditor({
      order_type: '',
      order_items: [],
      order_applications: [],
      dtf_roll_lines: [],
      dtf_piece_lines: [],
    })

    expect(container.textContent).toContain('Выберите тип заказа')
    expect(visibleSelectData(container)[0]).toEqual({
      placeholder: 'Выберите тип заказа',
      options: [
        { label: 'Печать на изделиях', value: 'Product Printing' },
        { label: 'DTF в рулоне', value: 'DTF Roll' },
        { label: 'DTF поштучно', value: 'DTF Pieces' },
        { label: 'Комбинированный', value: 'Combined' },
      ],
    })
    expectNoUserFacingEnglish(container)
  })

  it('renders a filled item and application with every localized Select option', () => {
    const container = mountEditor({
      order_type: 'Product Printing',
      currency: 'RUB',
      order_items: [
        {
          item_key: 'item-1780000000000',
          item_name: 'Худи оверсайз',
          supply_type: 'Studio Product',
          product: 'PROD-001',
          qty: 2,
          manual_rate: 1500,
          use_manual_rate: 1,
          discount_percentage: 5,
        },
      ],
      order_applications: [
        {
          item_key: 'item-1780000000000',
          production_type: 'DTF Printing',
          placement: 'Back',
          qty: 2,
          rate: 300,
        },
      ],
      dtf_roll_lines: [],
      dtf_piece_lines: [],
    })
    const selects = visibleSelectData(container)

    expect(selects.every(({ placeholder }) => placeholder)).toBe(true)
    expect(selects.flatMap(({ options }) => options)).toEqual(
      expect.arrayContaining([
        { label: 'Изделие клиента', value: 'Customer Item' },
        { label: 'Товар студии', value: 'Studio Product' },
        { label: 'Худи оверсайз', value: 'item-1780000000000' },
        { label: 'DTF-печать', value: 'DTF Printing' },
        { label: 'Шелкография', value: 'Screen Printing' },
        { label: 'Вышивка', value: 'Embroidery' },
        { label: 'Сублимация', value: 'Sublimation' },
        { label: 'Термоперенос', value: 'Heat Transfer Printing' },
        {
          label: 'Подготовка и правка макета',
          value: 'Artwork Preparation',
        },
        { label: 'Комбинированное нанесение', value: 'Combined' },
        { label: 'Грудь', value: 'Chest' },
        { label: 'Спина', value: 'Back' },
        { label: 'Рукав', value: 'Sleeve' },
        { label: 'Бирка / внутренняя часть', value: 'Tag / Inner Part' },
        { label: 'Другое', value: 'Other' },
      ]),
    )
    expect(container.textContent).not.toContain('Указать цену вручную')
    expect(container.textContent).not.toContain('item-1780000000000')
    expectNoUserFacingEnglish(container)
  })

  it('renders a filled roll with localized manual controls', () => {
    const container = mountEditor({
      order_type: 'DTF Roll',
      currency: 'RUB',
      order_items: [],
      order_applications: [],
      dtf_roll_lines: [
        {
          length_m: 3,
          rate_per_meter: 500,
          manual_amount: 1400,
          use_manual_amount: 1,
          comment: 'Срочно',
        },
      ],
      dtf_piece_lines: [],
    })

    expect(container.textContent).toContain('Цена за метр')
    expect(container.textContent).toContain('Указать сумму вручную')
    expect(
      container.querySelector('input[placeholder="Комментарий"]'),
    ).not.toBeNull()
    expectNoUserFacingEnglish(container)
  })

  it('renders filled DTF pieces with localized sizing options and raw formats', () => {
    const container = mountEditor({
      order_type: 'DTF Pieces',
      currency: 'RUB',
      order_items: [],
      order_applications: [],
      dtf_roll_lines: [],
      dtf_piece_lines: [
        {
          sizing_mode: 'Format',
          sheet_format: 'A4',
          qty: 10,
          unit_price: 100,
          manual_amount: 900,
          use_manual_amount: 1,
        },
      ],
    })
    const options = visibleSelectData(container).flatMap(
      ({ options }) => options,
    )

    expect(options).toEqual(
      expect.arrayContaining([
        { label: 'Формат', value: 'Format' },
        { label: 'Свой размер', value: 'Custom Size' },
        { label: 'Только количество', value: 'Quantity Only' },
        { label: 'A6', value: 'A6' },
        { label: 'A5', value: 'A5' },
        { label: 'A4', value: 'A4' },
        { label: 'A3', value: 'A3' },
        { label: 'A3+', value: 'A3+' },
        { label: 'A3++', value: 'A3++' },
      ]),
    )
    expect(container.textContent).toContain('Указать сумму вручную')
    expectNoUserFacingEnglish(container)
  })
})
