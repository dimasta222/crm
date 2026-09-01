import { createApp, defineComponent, h, nextTick, reactive } from 'vue'
import FieldLayout from '@/components/FieldLayout/FieldLayout.vue'
import FieldLayoutEditor from '@/components/FieldLayoutEditor.vue'

vi.mock('@/data/document', () => ({
  useDocument: () => ({ document: { fieldPropertyOverrides: {} } }),
}))

vi.mock('@/components/FieldLayout/Section.vue', async () => {
  const { defineComponent, h } = await import('vue')
  return {
    default: defineComponent({
      props: ['section'],
      setup(props) {
        return () => h('div', { 'data-section': props.section.name })
      },
    }),
  }
})

vi.mock('@/components/Icons/DragVerticalIcon.vue', () => ({
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

vi.mock('@/stores/meta', () => ({
  getMeta: () => ({ getFields: () => [] }),
}))

vi.mock('@/stores/global', () => ({
  globalStore: () => ({ $dialog: vi.fn() }),
}))

const layoutTestState = vi.hoisted(() => ({ randomId: 0 }))
vi.mock('@/utils', () => ({
  getRandom: () => String(++layoutTestState.randomId),
}))

vi.mock('vuedraggable', async () => {
  const { defineComponent, h } = await import('vue')
  return {
    default: defineComponent({
      props: ['list'],
      setup(props, { slots }) {
        return () =>
          h('div', [
            ...(props.list || []).flatMap(
              (element, index) => slots.item?.({ element, index }) || [],
            ),
            slots.footer?.(),
          ])
      },
    }),
  }
})

vi.mock('frappe-ui', async () => {
  const { defineComponent, h } = await import('vue')
  const Tabs = defineComponent({
    props: ['tabs', 'modelValue'],
    emits: ['update:modelValue'],
    setup(props, { emit, slots }) {
      return () =>
        h('div', [
          h(
            'div',
            { role: 'tablist' },
            props.tabs.map((tab, index) =>
              h(
                'button',
                {
                  role: 'tab',
                  onClick: () => emit('update:modelValue', index),
                },
                tab.label,
              ),
            ),
          ),
          slots['tab-panel']?.({ tab: props.tabs[props.modelValue] }),
        ])
    },
  })
  const Dropdown = defineComponent({
    setup(_, { slots }) {
      return () => h('div', slots.default?.())
    },
  })
  return { Dropdown, Tabs }
})

const ButtonStub = defineComponent({
  props: ['label'],
  setup(props, { attrs, slots }) {
    return () =>
      h(
        'button',
        { ...attrs, 'data-label': props.label },
        slots.default?.() || props.label,
      )
  },
})

function mount(component, props, components = {}) {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const app = createApp({ render: () => h(component, props) })
  app.config.globalProperties.__ = globalThis.__
  app.component('Button', ButtonStub)
  app.component('Input', { template: '<input />' })
  app.component('FeatherIcon', { template: '<span />' })
  Object.entries(components).forEach(([name, value]) =>
    app.component(name, value),
  )
  app.mount(container)
  return {
    container,
    unmount() {
      app.unmount()
      container.remove()
    },
  }
}

function dealTabs() {
  return ['details', 'production', 'payment', 'source'].map((name, index) => ({
    name,
    label: index === 0 ? '' : name[0].toUpperCase() + name.slice(1),
    sections: [{ name: `${name}_section`, columns: [] }],
  }))
}

describe('Data layout tab navigation', () => {
  it('navigates Details/Production/Payment/Source without mutating layout labels', async () => {
    const tabs = dealTabs()
    const original = structuredClone(tabs)
    const view = mount(FieldLayout, {
      tabs,
      data: {},
      doctype: 'CRM Deal',
      context: { fieldPropertyOverrides: {} },
    })
    const tabButtons = [...view.container.querySelectorAll('[role="tab"]')]

    expect(tabButtons.map((button) => button.textContent)).toEqual([
      'Details',
      'Production',
      'Payment',
      'Source',
    ])
    tabButtons[1].click()
    await nextTick()
    expect(view.container.querySelector('[data-section]').dataset.section).toBe(
      'production_section',
    )
    tabButtons[2].click()
    await nextTick()
    expect(view.container.querySelector('[data-section]').dataset.section).toBe(
      'payment_section',
    )
    tabButtons[3].click()
    await nextTick()
    expect(view.container.querySelector('[data-section]').dataset.section).toBe(
      'source_section',
    )
    tabButtons[0].click()
    await nextTick()
    expect(view.container.querySelector('[data-section]').dataset.section).toBe(
      'details_section',
    )
    expect(tabs).toEqual(original)
    view.unmount()
  })

  it('does not add the Deal Data-tab fallback to a single tab', () => {
    const tabs = [
      {
        name: 'details',
        label: '',
        sections: [{ name: 'details_section', columns: [] }],
      },
    ]
    const view = mount(FieldLayout, {
      tabs,
      data: {},
      doctype: 'CRM Deal',
      context: { fieldPropertyOverrides: {} },
    })

    expect(view.container.textContent).not.toContain('Details')
    expect(tabs[0].label).toBe('')
    view.unmount()
  })

  it('does not add the Deal Data-tab fallback to another DocType', () => {
    const tabs = dealTabs().slice(0, 2)
    const view = mount(FieldLayout, {
      tabs,
      data: {},
      doctype: 'CRM Lead',
      context: { fieldPropertyOverrides: {} },
    })

    const labels = [...view.container.querySelectorAll('[role="tab"]')].map(
      (button) => button.textContent,
    )
    expect(labels).toEqual(['', 'Production'])
    expect(tabs[0].label).toBe('')
    view.unmount()
  })

  it.each([
    ['CRM Deal', 'Details'],
    ['CRM Lead', 'Untitled'],
  ])(
    'keeps editor/render fallback consistent for %s',
    (doctype, editorLabel) => {
      const tabs = dealTabs().slice(0, 2)
      const rendered = mount(FieldLayout, {
        tabs,
        data: {},
        doctype,
        context: { fieldPropertyOverrides: {} },
      })
      const edited = mount(FieldLayoutEditor, {
        modelValue: tabs,
        doctype,
      })

      const renderLabel =
        rendered.container.querySelector('[role="tab"]').textContent
      expect(renderLabel).toBe(doctype === 'CRM Deal' ? 'Details' : '')
      expect(edited.container.textContent).toContain(editorLabel)
      expect(tabs[0].label).toBe('')

      rendered.unmount()
      edited.unmount()
    },
  )

  it('keeps existing editor tabs accessible and Add Tab only appends a tab', async () => {
    const state = reactive({ tabs: dealTabs() })
    const firstTab = JSON.parse(JSON.stringify(state.tabs[0]))
    const view = mount(FieldLayoutEditor, {
      doctype: 'CRM Deal',
      get modelValue() {
        return state.tabs
      },
      'onUpdate:modelValue': (value) => (state.tabs = value),
    })

    expect(view.container.textContent).toContain('Details')
    for (const label of ['Production', 'Payment', 'Source']) {
      const tab = [...view.container.querySelectorAll('div')].find(
        (element) => element.textContent.trim() === label,
      )
      expect(tab).toBeTruthy()
      const tabItem = tab.closest('.cursor-pointer')
      tabItem.click()
      await nextTick()
      expect(tabItem.className).toContain('bg-surface-base')
    }

    view.container.querySelector('[data-label="Add Tab"]').click()
    await nextTick()

    expect(state.tabs).toHaveLength(5)
    expect(state.tabs[0]).toEqual(firstTab)
    expect(state.tabs[4].label).toBe('New Tab')
    view.unmount()
  })
})
