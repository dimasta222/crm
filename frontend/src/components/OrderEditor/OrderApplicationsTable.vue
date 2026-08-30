<!-- eslint-disable vue/no-mutating-props -->
<template>
  <div class="border-t border-outline-gray-2 bg-surface-gray-1 px-3 py-3">
    <div class="mb-2 flex items-center justify-between gap-3">
      <div class="text-sm font-medium text-ink-gray-8">
        {{ __('Services and applications') }}
      </div>
      <Button
        :label="__('Add service')"
        icon-left="plus"
        size="sm"
        variant="subtle"
        @click="add"
      />
    </div>

    <div v-if="rows.length" class="order-grid overflow-x-auto">
      <table class="w-full min-w-[760px] text-sm">
        <thead>
          <tr>
            <th>{{ __('Production type') }}</th>
            <th>{{ __('Placement') }}</th>
            <th class="w-24 text-right">{{ __('Qty') }}</th>
            <th class="w-28 text-right">{{ __('Rate') }}</th>
            <th class="w-28 text-right">{{ __('Amount') }}</th>
            <th class="w-10" />
          </tr>
        </thead>
        <tbody>
          <template v-for="(row, index) in rows" :key="rowKey(row, index)">
            <tr>
              <td class="min-w-44">
                <Select
                  v-model="row.production_type"
                  :options="productionTypeOptions"
                  :placeholder="__('Select option')"
                  @update:model-value="
                    (productionType) =>
                      onProductionTypeChange(row, productionType)
                  "
                />
              </td>
              <td class="min-w-36">
                <Select
                  v-if="usesPlacement(row)"
                  v-model="row.placement"
                  :options="placementOptions"
                  :placeholder="__('Select option')"
                />
                <span v-else class="px-2 text-sm text-ink-gray-5">—</span>
              </td>
              <td>
                <FormControl v-model="row.qty" type="number" min="0" />
              </td>
              <td>
                <FormControl v-model="row.rate" type="number" min="0" />
              </td>
              <td class="text-right font-medium text-ink-gray-8">
                {{ formatAmount(calculateApplicationAmount(row, precision)) }}
              </td>
              <td>
                <Button
                  :tooltip="__('Delete row')"
                  icon="trash-2"
                  size="sm"
                  variant="ghost"
                  @click="remove(row)"
                />
              </td>
            </tr>
            <tr>
              <td colspan="6" class="!p-3">
                <div
                  class="grid grid-cols-1 gap-3 rounded-md bg-surface-white p-3 sm:grid-cols-2 lg:grid-cols-4"
                >
                  <FormControl
                    v-if="usesDimensions(row)"
                    v-model="row.width_cm"
                    type="number"
                    min="0"
                    :label="__('Width (cm)')"
                    :placeholder="__('Optional')"
                  />
                  <FormControl
                    v-if="usesDimensions(row)"
                    v-model="row.height_cm"
                    type="number"
                    min="0"
                    :label="__('Height (cm)')"
                    :placeholder="__('Optional')"
                  />
                  <FormControl
                    v-if="row.production_type === 'Embroidery'"
                    v-model="row.embroidery_setup_fee"
                    type="number"
                    min="0"
                    :label="__('Embroidery artwork preparation')"
                  />
                  <FormControl
                    v-if="row.production_type === 'Screen Printing'"
                    v-model="row.screen_color_count"
                    type="number"
                    min="0"
                    :label="__('Number of colors')"
                    :placeholder="__('Optional')"
                  />
                  <div v-if="row.production_type === 'Screen Printing'">
                    <div class="mb-1 text-xs text-ink-gray-5">
                      {{ __('Fabric type') }}
                    </div>
                    <Select
                      v-model="row.fabric_type"
                      :options="fabricTypeOptions"
                      :placeholder="__('Select option')"
                    />
                  </div>
                  <FormControl
                    v-model="row.comment"
                    type="text"
                    :label="__('Comment')"
                    :placeholder="__('Comment for this service')"
                    class="lg:col-span-2"
                  />
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
    <div v-else class="order-grid-empty">
      {{ __('No applications added') }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Button, FormControl, Select } from 'frappe-ui'
import { getMeta } from '@/stores/meta'
import {
  calculateApplicationAmount,
  getOrderCurrencyPrecision,
} from '@/utils/orderEditor'

const props = defineProps({
  doc: { type: Object, required: true },
  itemKey: { type: String, default: '' },
})
const allRows = computed(() => props.doc.order_applications || [])
const items = computed(() => props.doc.order_items || [])
const rows = computed(() =>
  props.itemKey
    ? allRows.value.filter((row) => row.item_key === props.itemKey)
    : allRows.value,
)
let editorKeySequence = 0
const { doctypeMeta } = getMeta('CRM Deal')
const precision = computed(() =>
  getOrderCurrencyPrecision(
    doctypeMeta.value?.fields?.find(
      (field) => field.fieldname === 'order_total',
    ),
    window.sysdefaults,
  ),
)
const productionTypeOptions = [
  'DTF Printing',
  'Screen Printing',
  'Embroidery',
  'Sublimation',
  'Heat Transfer Printing',
  'Artwork Preparation',
  'Combined',
].map((value) => ({ label: __(value), value }))
const placementOptions = [
  { label: __('Chest'), value: 'Chest' },
  { label: __('Back placement'), value: 'Back' },
  { label: __('Sleeve'), value: 'Sleeve' },
  { label: __('Tag / Inner Part'), value: 'Tag / Inner Part' },
  { label: __('Other'), value: 'Other' },
]
const fabricTypeOptions = [
  { label: __('White'), value: 'White' },
  { label: __('Dark'), value: 'Dark' },
  { label: __('Colored'), value: 'Colored' },
]

function rowKey(row, index) {
  if (row.name) return row.name
  if (!row._editorKey) {
    editorKeySequence += 1
    Object.defineProperty(row, '_editorKey', {
      value: `application-${editorKeySequence}-${index}`,
      enumerable: false,
    })
  }
  return row._editorKey
}

function usesPlacement(row) {
  return !['Artwork Preparation', 'Sublimation'].includes(row.production_type)
}

function usesDimensions(row) {
  return !['Artwork Preparation', 'Sublimation'].includes(row.production_type)
}

function onProductionTypeChange(row, productionType) {
  row.production_type = productionType
  if (!usesPlacement(row)) row.placement = 'Other'
}

function remove(row) {
  const index = allRows.value.indexOf(row)
  if (index !== -1) allRows.value.splice(index, 1)
}

function formatAmount(value) {
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: props.doc.currency || 'RUB',
    minimumFractionDigits: precision.value,
    maximumFractionDigits: precision.value,
  }).format(value)
}

function add() {
  const item = props.itemKey
    ? items.value.find((candidate) => candidate.item_key === props.itemKey)
    : items.value[0]
  if (!item) return
  allRows.value.push({
    item_key: item.item_key,
    production_type: 'DTF Printing',
    placement: 'Chest',
    qty: item.qty || 1,
    rate: 0,
    comment: '',
  })
}
</script>

<style scoped>
@import './orderEditor.css';
</style>
