<!-- eslint-disable vue/no-mutating-props -->
<template>
  <section
    data-testid="order-totals-card"
    class="order-totals-card overflow-hidden rounded-xl border border-outline-gray-2 bg-surface-cards text-sm"
  >
    <div
      class="order-totals-header border-b border-outline-gray-2 px-5 py-4 text-base font-semibold text-ink-gray-9"
    >
      {{ __('Preliminary calculation') }}
    </div>

    <div class="px-5 py-5">
      <dl class="grid grid-cols-1 gap-x-10 gap-y-2 sm:grid-cols-2">
        <div
          v-for="row in totalsRows"
          :key="row.label"
          class="flex items-center justify-between gap-4"
        >
          <dt class="text-ink-gray-5">{{ __(row.label) }}</dt>
          <dd class="font-medium text-ink-gray-8">{{ format(row.value) }}</dd>
        </div>
        <div
          class="mt-1 flex items-center justify-between gap-4 border-t border-outline-gray-2 pt-3 sm:col-span-2"
        >
          <dt class="font-medium text-ink-gray-7">{{ __('Subtotal') }}</dt>
          <dd class="font-semibold text-ink-gray-9">
            {{ format(preview.subtotal) }}
          </dd>
        </div>
      </dl>

      <div
        class="mt-4 grid grid-cols-1 items-end gap-4 rounded-xl border border-outline-amber-1 bg-surface-amber-1/40 p-4 sm:grid-cols-2"
      >
        <FormControl
          v-model="doc.order_discount_percentage"
          type="number"
          min="0"
          max="100"
          step="0.01"
          :label="__('Order discount, %')"
        />
        <div class="flex items-center justify-between gap-4 sm:justify-end">
          <span class="text-ink-gray-5">{{ __('Discount') }}</span>
          <span class="font-semibold text-ink-amber-3">
            {{ format(-preview.discountAmount) }}
          </span>
        </div>
      </div>

      <div
        class="mt-4 rounded-xl border border-outline-gray-2 bg-surface-gray-1/70 p-4"
      >
        <Checkbox
          v-model="doc.use_manual_total"
          :label="__('Set amount manually')"
        />
        <FormControl
          v-if="doc.use_manual_total"
          v-model="doc.manual_order_total"
          class="mt-3 max-w-64"
          type="number"
          min="0"
          step="0.01"
          :label="__('Order total')"
          :placeholder="__('Enter amount')"
        />
      </div>

      <div
        class="order-totals-final mt-4 flex items-center justify-between gap-4 rounded-xl border border-outline-gray-2 px-4 py-4"
      >
        <span class="font-semibold text-ink-gray-8">{{ __('Order total') }}</span>
        <span class="text-xl font-semibold text-ink-gray-9">
          {{ format(preview.orderTotal) }}
        </span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, watchEffect } from 'vue'
import { Checkbox, FormControl } from 'frappe-ui'
import { getMeta } from '@/stores/meta'
import {
  calculateOrderPreview,
  getOrderCurrencyPrecision,
  synchronizeOrderSummary,
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
watchEffect(() => synchronizeOrderSummary(props.doc, precision.value))
const totalsRows = computed(() => {
  const rows = []
  if (['Product Printing', 'Combined'].includes(props.doc.order_type)) {
    rows.push(
      { label: 'Items cost', value: preview.value.itemsSubtotal },
      { label: 'Applications cost', value: preview.value.applicationsSubtotal },
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

<style scoped>
.order-totals-card {
  box-shadow: 0 14px 34px rgb(0 0 0 / 0.08);
}

.order-totals-header {
  background: linear-gradient(
    90deg,
    rgb(var(--surface-violet-1) / 0.58),
    rgb(var(--surface-cards)) 72%
  );
}

.order-totals-final {
  background: linear-gradient(
    90deg,
    rgb(var(--surface-violet-1) / 0.52),
    rgb(var(--surface-blue-1) / 0.28)
  );
}
</style>
