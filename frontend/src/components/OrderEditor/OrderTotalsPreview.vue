<!-- eslint-disable vue/no-mutating-props -->
<template>
  <div class="rounded bg-surface-gray-2 p-3 text-sm">
    <div class="mb-2 font-medium text-ink-gray-8">
      {{ __('Live order preview') }}
    </div>
    <dl class="grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-3">
      <template v-for="row in totalsRows" :key="row.label"
        ><dt class="text-ink-gray-6">{{ __(row.label) }}</dt>
        <dd class="text-right font-medium">
          {{ format(row.value) }}
        </dd></template
      >
    </dl>
    <label class="mt-3 flex items-center gap-2"
      ><input v-model="doc.use_manual_total" type="checkbox" />
      {{ __('Manual order total override') }}</label
    ><input
      v-if="doc.use_manual_total"
      v-model.number="doc.manual_order_total"
      type="number"
      class="mt-2 rounded border border-outline-gray-2 px-2 py-1"
    />
    <p v-if="doc.use_manual_total" class="mt-1 text-xs text-ink-amber-3">
      {{ __('Manual override — server validation still applies.') }}
    </p>
  </div>
</template>
<script setup>
import { computed } from 'vue'
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
const totalsRows = computed(() => [
  { label: 'Items subtotal', value: preview.value.itemsSubtotal },
  { label: 'Applications subtotal', value: preview.value.applicationsSubtotal },
  { label: 'DTF Roll subtotal', value: preview.value.dtfRollSubtotal },
  { label: 'DTF Pieces subtotal', value: preview.value.dtfPieceSubtotal },
  { label: 'Discount Amount', value: preview.value.discountAmount },
  { label: 'Subtotal', value: preview.value.subtotal },
  { label: 'Order Total', value: preview.value.orderTotal },
])
function format(value) {
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: props.doc.currency || 'USD',
    minimumFractionDigits: precision.value,
    maximumFractionDigits: precision.value,
  }).format(value)
}
</script>
