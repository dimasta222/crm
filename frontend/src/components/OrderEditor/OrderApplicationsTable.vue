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

    <div v-if="rows.length" class="space-y-3">
      <div
        v-for="(row, index) in rows"
        :key="rowKey(row, index)"
        data-testid="order-service-card"
        class="overflow-hidden rounded-md border border-outline-gray-2 border-l-4 border-l-outline-gray-4 bg-surface-white"
      >
        <div
          class="flex flex-wrap items-center justify-between gap-3 border-b border-outline-gray-2 bg-surface-gray-1 px-3 py-2.5"
        >
          <div>
            <div class="text-sm font-medium text-ink-gray-8">
              №{{ index + 1 }} · {{ __(row.production_type || 'Service') }}
            </div>
            <div
              v-if="usesPlacement(row) && row.placement"
              class="mt-0.5 text-xs text-ink-gray-5"
            >
              {{ placementLabel(row.placement) }}
            </div>
          </div>
          <div class="flex items-center gap-2">
            <div class="text-right">
              <div class="text-xs text-ink-gray-5">{{ __('Amount') }}</div>
              <div class="font-medium text-ink-gray-8">
                {{ formatAmount(calculateApplicationAmount(row, precision)) }}
              </div>
            </div>
            <Button
              :tooltip="__('Delete row')"
              icon="trash-2"
              size="sm"
              variant="ghost"
              @click="remove(row)"
            />
          </div>
        </div>

        <div
          class="grid grid-cols-1 items-start gap-3 p-3 sm:grid-cols-2 lg:grid-cols-4"
        >
          <div class="min-w-0">
            <div class="mb-1 h-4 whitespace-nowrap text-xs text-ink-gray-5">
              {{ __('Production type') }}
            </div>
            <Select
              v-model="row.production_type"
              :options="productionTypeOptions"
              :placeholder="__('Select option')"
              @update:model-value="
                (productionType) =>
                  onProductionTypeChange(row, productionType)
              "
            />
          </div>
          <div v-if="usesPlacement(row)" class="min-w-0">
            <div class="mb-1 h-4 whitespace-nowrap text-xs text-ink-gray-5">
              {{ __('Placement') }}
            </div>
            <Select
              v-model="row.placement"
              :options="placementOptions"
              :placeholder="__('Select option')"
            />
          </div>
          <FormControl
            v-model="row.qty"
            type="number"
            min="0"
            :label="__('Qty')"
          />
          <FormControl
            v-model="row.rate"
            type="number"
            min="0"
            step="0.01"
            :label="__('Rate')"
          />
          <FormControl
            v-if="usesDimensions(row)"
            v-model="row.width_cm"
            type="number"
            min="0"
            :label="__('Width (cm)')"
          />
          <FormControl
            v-if="usesDimensions(row)"
            v-model="row.height_cm"
            type="number"
            min="0"
            :label="__('Height (cm)')"
          />
          <FormControl
            v-if="row.production_type === 'Embroidery'"
            v-model="row.embroidery_setup_fee"
            type="number"
            min="0"
            step="0.01"
            :label="__('Embroidery artwork preparation')"
          />
          <FormControl
            v-if="row.production_type === 'Screen Printing'"
            v-model="row.screen_color_count"
            type="number"
            min="0"
            :label="__('Number of colors')"
          />
          <div v-if="row.production_type === 'Screen Printing'" class="min-w-0">
            <div class="mb-1 h-4 whitespace-nowrap text-xs text-ink-gray-5">
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
            class="sm:col-span-2"
          />
        </div>
      </div>
    </div>
    <div
      v-else
      class="rounded-md border border-dashed border-outline-gray-2 bg-surface-white px-4 py-5 text-center text-sm text-ink-gray-5"
    >
      {{ __('No applications added') }}
    </div>
  </div>
</template>

<script setup>
import { computed, watch } from 'vue'
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

function placementLabel(value) {
  return (
    placementOptions.find((option) => option.value === value)?.label || value
  )
}

function clearLegacyZeroDimensions(currentRows) {
  currentRows.forEach((row) => {
    if (Number(row.width_cm) === 0) row.width_cm = null
    if (Number(row.height_cm) === 0) row.height_cm = null
  })
}

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
    width_cm: null,
    height_cm: null,
    comment: '',
  })
}

watch(rows, clearLegacyZeroDimensions, { immediate: true })
</script>

<style scoped>
@import './orderEditor.css';
</style>
