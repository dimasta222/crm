import { createApp, defineComponent, h, nextTick } from 'vue'
import Filter from '@/components/Filter.vue'
import KanbanView from '@/components/Kanban/KanbanView.vue'

const testState = vi.hoisted(() => ({
  filterFields: [],
  dragEvent: null,
  toastError: vi.fn(),
}))

vi.mock('@/composables/settings', async () => {
  const { ref } = await import('vue')
  return { isMobileView: ref(false) }
})

vi.mock('@/utils', () => ({
  colors: ['gray'],
  isTouchScreenDevice: () => false,
  parseColor: (color) => color,
}))

vi.mock('@/components/Icons/FilterIcon.vue', () => ({
  default: { template: '<span />' },
}))
vi.mock('@/components/Icons/RefreshIcon.vue', () => ({
  default: { template: '<span />' },
}))
vi.mock('@/components/Icons/IndicatorIcon.vue', () => ({
  default: { template: '<span />' },
}))
vi.mock('@/components/frappe-ui/Autocomplete.vue', async () => {
  const { defineComponent, h } = await import('vue')
  return {
    default: defineComponent({
      setup(_, { slots }) {
        return () => h('div', slots.target?.({ togglePopover: () => {} }))
      },
    }),
  }
})

vi.mock('frappe-ui', async () => {
  const { defineComponent, h } = await import('vue')
  const SlotContainer = defineComponent({
    setup(_, { slots }) {
      return () =>
        h('div', [
          slots.target?.({ togglePopover: () => {}, close: () => {} }),
          slots.default?.(),
          slots.body?.({ close: () => {} }),
        ])
    },
  })
  const FormControl = defineComponent({
    props: ['options', 'modelValue', 'type'],
    emits: ['update:modelValue', 'change'],
    setup(props, { emit }) {
      return () =>
        h(
          'div',
          { 'data-testid': 'form-control' },
          (props.options || []).map((option) => {
            const normalized =
              typeof option === 'string'
                ? { label: option, value: option }
                : option
            return h(
              'button',
              {
                'data-option-label': normalized.label,
                'data-option-value': normalized.value,
                onClick: () => emit('update:modelValue', normalized.value),
              },
              normalized.label,
            )
          }),
        )
    },
  })
  return {
    createResource: () => ({
      data: testState.filterFields,
      fetch: vi.fn(),
    }),
    FormControl,
    Popover: SlotContainer,
    Dropdown: SlotContainer,
    DatePicker: FormControl,
    DateTimePicker: FormControl,
    DateRangePicker: FormControl,
    toast: { error: testState.toastError },
  }
})

vi.mock('vuedraggable', async () => {
  const { defineComponent, h } = await import('vue')
  return {
    default: defineComponent({
      inheritAttrs: false,
      props: ['list', 'disabled'],
      emits: ['end'],
      setup(props, { attrs, emit, slots }) {
        return () =>
          h(
            'div',
            {
              'data-column': attrs['data-column'],
              'data-disabled': String(props.disabled),
            },
            [
              ...(props.list || []).flatMap(
                (element) => slots.item?.({ element }) || [],
              ),
              attrs['data-column']
                ? h(
                    'button',
                    {
                      'data-testid': `move-${attrs['data-column']}`,
                      onClick: () => emit('end', testState.dragEvent),
                    },
                    'move',
                  )
                : null,
            ],
          )
      },
    }),
  }
})

const ButtonStub = defineComponent({
  props: ['label'],
  setup(props, { attrs, slots }) {
    return () => h('button', attrs, slots.default?.() || props.label)
  },
})

function mount(component, props) {
  const container = document.createElement('div')
  document.body.append(container)
  const app = createApp({ render: () => h(component, props) })
  app.config.globalProperties.__ = globalThis.__
  app.component('Button', ButtonStub)
  app.mount(container)
  return {
    container,
    unmount() {
      app.unmount()
      container.remove()
    },
  }
}

function filterList(fieldname, value) {
  return {
    params: { filters: { [fieldname]: value } },
    data: { params: { filters: { [fieldname]: value } } },
  }
}

function kanbanModel(columnField, names) {
  return {
    params: { column_field: columnField },
    data: {
      view_type: 'kanban',
      title_field: 'title',
      kanban_columns: [],
      data: names.map((name, index) => ({
        column: { name, count: 1, all_count: 1 },
        data: [{ name: `ORDER-${index + 1}`, title: `Order ${index + 1}` }],
        fields: [],
      })),
    },
  }
}

describe('payment status component events preserve raw values', () => {
  const originalTranslate = globalThis.__
  const translations = {
    Paid: 'Оплачено',
    Unpaid: 'Не оплачено',
    Deal: 'Заказ',
    'In Progress': 'В работе',
  }

  beforeEach(() => {
    globalThis.__ = (message) => translations[message] || message
  })

  afterEach(() => {
    globalThis.__ = originalTranslate
    testState.filterFields = []
    testState.dragEvent = null
    testState.toastError.mockReset()
    document.body.innerHTML = ''
  })

  it('Filter displays a translated payment label but emits Paid', async () => {
    testState.filterFields = [
      {
        label: 'Payment Status',
        fieldname: 'payment_status',
        fieldtype: 'Select',
        options: 'Paid\nUnpaid',
      },
    ]
    const update = vi.fn()
    const view = mount(Filter, {
      doctype: 'CRM Deal',
      modelValue: filterList('payment_status', 'Unpaid'),
      default_filters: {},
      onUpdate: update,
    })
    const paid = view.container.querySelector('[data-option-value="Paid"]')
    expect(paid.dataset.optionLabel).toBe('Оплачено')
    paid.click()
    await nextTick()
    expect(update).toHaveBeenLastCalledWith({ payment_status: 'Paid' })
    view.unmount()
  })

  it('Filter displays and emits an arbitrary raw Select value', async () => {
    testState.filterFields = [
      {
        label: 'Custom category',
        fieldname: 'custom_category',
        fieldtype: 'Select',
        options: 'Deal',
      },
    ]
    const update = vi.fn()
    const view = mount(Filter, {
      doctype: 'CRM Deal',
      modelValue: filterList('custom_category', 'Deal'),
      default_filters: {},
      onUpdate: update,
    })
    const deal = view.container.querySelector('[data-option-value="Deal"]')
    expect(deal.dataset.optionLabel).toBe('Deal')
    deal.click()
    await nextTick()
    expect(update).toHaveBeenLastCalledWith({ custom_category: 'Deal' })
    view.unmount()
  })

  it('Kanban translates payment headers but emits the raw target column', async () => {
    const update = vi.fn()
    testState.dragEvent = {
      to: { dataset: { column: 'Paid' } },
      from: { dataset: { column: 'Unpaid' } },
      item: { dataset: { name: 'ORDER-1' } },
    }
    const view = mount(KanbanView, {
      modelValue: kanbanModel('payment_status', ['Unpaid', 'Paid']),
      options: { onNewClick: vi.fn() },
      onUpdate: update,
    })
    expect(view.container.textContent).toContain('Не оплачено')
    expect(view.container.textContent).toContain('Оплачено')
    view.container.querySelector('[data-testid="move-Unpaid"]').click()
    await nextTick()
    expect(update).toHaveBeenLastCalledWith(
      expect.objectContaining({ item: 'ORDER-1', to: 'Paid' }),
    )
    view.unmount()
  })

  it('Kanban translates an order status and emits its raw value', async () => {
    const update = vi.fn()
    testState.dragEvent = {
      to: { dataset: { column: 'In Progress' } },
      from: { dataset: { column: 'Other' } },
      item: { dataset: { name: 'ORDER-3' } },
    }
    const view = mount(KanbanView, {
      modelValue: kanbanModel('status', ['Other', 'In Progress']),
      options: { onNewClick: vi.fn() },
      onUpdate: update,
    })
    expect(view.container.textContent).toContain('В работе')
    view.container.querySelector('[data-testid="move-Other"]').click()
    await nextTick()
    expect(update).toHaveBeenLastCalledWith(
      expect.objectContaining({ item: 'ORDER-3', to: 'In Progress' }),
    )
    view.unmount()
  })

  it('Kanban translates an arbitrary Deal column and keeps its raw event', async () => {
    const update = vi.fn()
    testState.dragEvent = {
      to: { dataset: { column: 'Deal' } },
      from: { dataset: { column: 'Other' } },
      item: { dataset: { name: 'ORDER-2' } },
    }
    const view = mount(KanbanView, {
      modelValue: kanbanModel('custom_category', ['Deal', 'Other']),
      options: { onNewClick: vi.fn() },
      onUpdate: update,
    })
    expect(view.container.textContent).toContain('Заказ')
    view.container.querySelector('[data-testid="move-Other"]').click()
    await nextTick()
    expect(update).toHaveBeenLastCalledWith(
      expect.objectContaining({ item: 'ORDER-2', to: 'Deal' }),
    )
    view.unmount()
  })

  it('Kanban applies a move only after the server confirms it', async () => {
    let confirmMove
    const onMove = vi.fn(
      () => new Promise((resolve) => (confirmMove = resolve)),
    )
    const model = kanbanModel('status', ['Open', 'Won'])
    testState.dragEvent = {
      to: { dataset: { column: 'Won' } },
      from: { dataset: { column: 'Open' } },
      item: { dataset: { name: 'ORDER-1' } },
      oldIndex: 0,
      newIndex: 0,
    }
    const view = mount(KanbanView, {
      modelValue: model,
      options: { onNewClick: vi.fn(), onMove },
    })

    view.container.querySelector('[data-testid="move-Open"]').click()
    await nextTick()

    expect(onMove).toHaveBeenCalledWith(
      expect.objectContaining({
        item: 'ORDER-1',
        from: 'Open',
        to: 'Won',
        fieldname: 'status',
      }),
    )
    expect(model.data.data[0].data.map((item) => item.name)).toContain(
      'ORDER-1',
    )
    expect(model.data.data[1].data.map((item) => item.name)).not.toContain(
      'ORDER-1',
    )

    confirmMove()
    await nextTick()
    await nextTick()

    expect(model.data.data[0].data.map((item) => item.name)).not.toContain(
      'ORDER-1',
    )
    expect(model.data.data[1].data.map((item) => item.name)).toContain(
      'ORDER-1',
    )
    view.unmount()
  })

  it('Kanban locks DnD only while a deferred server request is running', async () => {
    let startServerRequest
    let finishMove
    const move = new Promise((resolve) => (finishMove = resolve))
    move.serverRequestStarted = new Promise(
      (resolve) => (startServerRequest = resolve),
    )
    const model = kanbanModel('status', ['Open', 'Lost'])
    testState.dragEvent = {
      to: { dataset: { column: 'Lost' } },
      from: { dataset: { column: 'Open' } },
      item: { dataset: { name: 'ORDER-1' } },
      oldIndex: 0,
      newIndex: 0,
    }
    const view = mount(KanbanView, {
      modelValue: model,
      options: { onNewClick: vi.fn(), onMove: vi.fn(() => move) },
    })

    view.container.querySelector('[data-testid="move-Open"]').click()
    await nextTick()
    expect(
      view.container.querySelector('[data-column="Open"]').dataset.disabled,
    ).toBe('false')

    startServerRequest(true)
    await Promise.resolve()
    await nextTick()
    expect(
      view.container.querySelector('[data-column="Open"]').dataset.disabled,
    ).toBe('true')

    finishMove(false)
    await nextTick()
    await nextTick()
    expect(
      view.container.querySelector('[data-column="Open"]').dataset.disabled,
    ).toBe('false')
    expect(model.data.data[0].data.map((item) => item.name)).toContain(
      'ORDER-1',
    )
    view.unmount()
  })

  it('Kanban rolls a move back and reports an API failure', async () => {
    const model = kanbanModel('status', ['Open', 'Won'])
    testState.dragEvent = {
      to: { dataset: { column: 'Won' } },
      from: { dataset: { column: 'Open' } },
      item: { dataset: { name: 'ORDER-1' } },
      oldIndex: 0,
      newIndex: 0,
    }
    const view = mount(KanbanView, {
      modelValue: model,
      options: {
        onNewClick: vi.fn(),
        onMove: vi.fn().mockRejectedValue({ messages: ['Access denied'] }),
      },
    })

    view.container.querySelector('[data-testid="move-Open"]').click()
    await nextTick()
    await nextTick()

    expect(model.data.data[0].data.map((item) => item.name)).toContain(
      'ORDER-1',
    )
    expect(model.data.data[1].data.map((item) => item.name)).not.toContain(
      'ORDER-1',
    )
    expect(
      view.container.querySelector('[data-column="Open"]').dataset.disabled,
    ).toBe('false')
    expect(testState.toastError).toHaveBeenCalledWith('Access denied')
    view.unmount()
  })
})
