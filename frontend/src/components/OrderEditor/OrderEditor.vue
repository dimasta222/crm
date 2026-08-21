<!-- eslint-disable vue/no-mutating-props -->
<template>
  <section
    class="mb-6 rounded-lg border border-outline-gray-2 bg-surface-white p-4"
  >
    <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 class="text-base font-semibold text-ink-gray-8">
          {{ __('Order') }}
        </h2>
        <p class="text-sm text-ink-gray-5">
          {{
            __(
              'Calculated locally; the server validates and recalculates on save.',
            )
          }}
        </p>
      </div>
      <label class="flex flex-col gap-1 text-sm font-medium text-ink-gray-7">
        {{ __('Order Type') }}
        <select
          v-model="doc.order_type"
          class="rounded border border-outline-gray-2 px-2 py-1.5"
        >
          <option value="">{{ __('Select order type') }}</option>
          <option v-for="type in orderTypes" :key="type" :value="type">
            {{ __(type) }}
          </option>
        </select>
      </label>
    </div>
    <div
      v-if="incompatible.length"
      class="mb-4 rounded bg-surface-amber-1 p-3 text-sm text-ink-amber-3"
    >
      {{
        __(
          'Existing {0} rows are incompatible with this order type. They were kept and will be finally validated by the server.',
          [incompatible.join(', ')],
        )
      }}
    </div>
    <OrderItemsTable v-if="showProducts" :doc="doc" />
    <OrderApplicationsTable v-if="showProducts" :doc="doc" />
    <DtfRollTable v-if="showRolls" :doc="doc" />
    <DtfPiecesTable v-if="showPieces" :doc="doc" />
    <OrderTotalsPreview :doc="doc" />
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { incompatibleOrderCategories } from '@/utils/orderEditor'
import DtfPiecesTable from './DtfPiecesTable.vue'
import DtfRollTable from './DtfRollTable.vue'
import OrderApplicationsTable from './OrderApplicationsTable.vue'
import OrderItemsTable from './OrderItemsTable.vue'
import OrderTotalsPreview from './OrderTotalsPreview.vue'

const props = defineProps({ doc: { type: Object, required: true } })
const orderTypes = ['Product Printing', 'DTF Roll', 'DTF Pieces', 'Combined']
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
