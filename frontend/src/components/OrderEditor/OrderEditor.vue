<!-- eslint-disable vue/no-mutating-props -->
<template>
  <section
    class="mb-6 rounded-lg border border-outline-gray-2 bg-surface-white px-4 py-3"
  >
    <Section
      :label="__('Order composition')"
      :collapsible="false"
      header-class="flex-wrap gap-3"
      label-class="font-semibold"
    >
      <template #actions>
        <div class="flex min-w-56 items-center gap-2">
          <span class="shrink-0 text-sm text-ink-gray-6">
            {{ __('Order type') }}
          </span>
          <Select
            v-model="doc.order_type"
            class="min-w-44"
            :options="orderTypeOptions"
            :placeholder="__('Select order type')"
          />
        </div>
      </template>

      <div
        v-if="incompatible.length"
        class="mt-3 rounded-md border border-outline-amber-2 bg-surface-amber-1 px-3 py-2 text-sm text-ink-amber-3"
      >
        {{
          __('The order retains rows from other types: {0}.', [
            incompatible.map((category) => __(category)).join(', '),
          ])
        }}
      </div>

      <div class="mt-4 space-y-4">
        <OrderItemsTable v-if="showProducts" :doc="doc" />
        <OrderApplicationsTable v-if="showProducts" :doc="doc" />
        <DtfRollTable v-if="showRolls" :doc="doc" />
        <DtfPiecesTable v-if="showPieces" :doc="doc" />
        <OrderTotalsPreview v-if="doc.order_type" :doc="doc" />
        <div
          v-else
          class="rounded-md border border-dashed border-outline-gray-2 bg-surface-gray-1 px-4 py-6 text-center text-sm text-ink-gray-5"
        >
          {{ __('Select order type') }}
        </div>
      </div>
    </Section>
  </section>
</template>

<script setup>
import Section from '@/components/Section.vue'
import { computed } from 'vue'
import { Select } from 'frappe-ui'
import { incompatibleOrderCategories } from '@/utils/orderEditor'
import DtfPiecesTable from './DtfPiecesTable.vue'
import DtfRollTable from './DtfRollTable.vue'
import OrderApplicationsTable from './OrderApplicationsTable.vue'
import OrderItemsTable from './OrderItemsTable.vue'
import OrderTotalsPreview from './OrderTotalsPreview.vue'

const props = defineProps({ doc: { type: Object, required: true } })
const orderTypeOptions = [
  { label: __('Product Printing'), value: 'Product Printing' },
  { label: __('DTF Roll'), value: 'DTF Roll' },
  { label: __('DTF Pieces'), value: 'DTF Pieces' },
  { label: __('Combined order'), value: 'Combined' },
]
const showProducts = computed(() =>
  ['Product Printing', 'Combined'].includes(props.doc.order_type),
)
const showRolls = computed(() =>
  ['DTF Roll', 'Combined'].includes(props.doc.order_type),
)
const showPieces = computed(() =>
  ['DTF Pieces', 'Combined'].includes(props.doc.order_type),
)
const incompatible = computed(() => incompatibleOrderCategories(props.doc))
</script>
