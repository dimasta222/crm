<!-- eslint-disable vue/no-mutating-props -->
<template>
  <section
    class="rounded-md border border-outline-gray-2 bg-surface-gray-1 px-3 py-2.5 text-sm"
  >
    <div class="mb-2 font-medium text-ink-gray-8">
      {{ __('Preliminary calculation') }}
    </div>
    <dl class="grid grid-cols-1 gap-x-8 gap-y-1 sm:grid-cols-2">
      <div
        v-for="row in totalsRows"
        :key="row.label"
        class="flex items-center justify-between gap-4"
      >
        <dt class="text-ink-gray-6">{{ __(row.label) }}</dt>
        <dd class="font-medium text-ink-gray-8">{{ format(row.value) }}</dd>
      </div>
      <div
        class="flex items-center justify-between gap-4 border-t border-outline-gray-2 pt-1 sm:col-span-2"
      >
        <dt class="font-medium text-ink-gray-8">{{ __('Total') }}</dt>
        <dd class="font-semibold text-ink-gray-9">
          {{ format(preview.orderTotal) }}
        </dd>
      </div>
    </dl>
    <div class="mt-2 border-t border-outline-gray-2 pt-2">
      <Checkbox
        v-model="doc.use_manual_total"
        :label="__('Set amount manually')"
      />
      <FormControl
        v-if="doc.use_manual_total"
        v-model="doc.manual_order_total"
        class="mt-2 max-w-48"
        type="number"
        min="0"
        :label="__('Order total')"
        :placeholder="__('Enter amount')"
      />
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { Checkbox, FormControl } from 'frappe-ui'
import { getMeta } from '@/stores/meta'
import {
  calculateOrderPreview,
  getOrderCurrencyPrecision,
} from '@/utils/orderEditor'

const props = defineProps({ doc: { type: Object, required: true } })
const { doctypeMeta } = getMeta('CRM Deal')
const precision = computed(() =>
  getOrderCurrencyPrecision(
    doctypeMeta.value?.fields?.find(
      (field) => field.fieldname === 'order_total',
    ),
    window.sysdefaults,
  ),
)
const preview = computed(() =>
  calculateOrderPreview(props.doc, precision.value),
)
const totalsRows = computed(() => {
  const rows = []
  if (['Product Printing', 'Combined'].includes(props.doc.order_type)) {
    rows.push(
      { label: 'Items cost', value: preview.value.itemsSubtotal },
      { label: 'Applications cost', value: preview.value.applicationsSubtotal },
      { label: 'Discount', value: preview.value.discountAmount },
    )
  }
  if (['DTF Roll', 'Combined'].includes(props.doc.order_type)) {
    rows.push({ label: 'DTF Roll cost', value: preview.value.dtfRollSubtotal })
  }
  if (['DTF Pieces', 'Combined'].includes(props.doc.order_type)) {
    rows.push({
      label: 'DTF Pieces cost',
      value: preview.value.dtfPieceSubtotal,
    })
  }
  return rows
})
function format(value) {
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: props.doc.currency || 'USD',
    minimumFractionDigits: precision.value,
    maximumFractionDigits: precision.value,
  }).format(value)
}
</script>
