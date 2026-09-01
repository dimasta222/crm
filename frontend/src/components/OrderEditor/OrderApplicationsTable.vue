<!-- eslint-disable vue/no-mutating-props -->
<template>
  <div class="bg-surface-gray-1/45 px-5 py-5">
    <div v-if="rows.length" class="space-y-4">
      <div
        v-for="(row, index) in rows"
        :key="rowKey(row, index)"
        data-testid="order-service-card"
        :data-service-tone="serviceTone(row)"
        :style="serviceCardStyle(row)"
        class="order-service-card overflow-hidden rounded-xl border border-outline-gray-2 border-l-[6px] bg-surface-elevation-1"
      >
        <div
          class="order-service-header flex flex-wrap items-center justify-between gap-4 border-b border-outline-gray-2 px-4 py-4"
        >
          <div class="min-w-0">
            <div class="text-sm font-semibold text-ink-gray-9">
              {{ __('Service') }} №{{ index + 1 }} ·
              {{ __(row.production_type || 'Service') }}
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
              <div class="text-base font-semibold text-ink-gray-9">
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
          class="grid grid-cols-1 items-start gap-x-5 gap-y-4 p-4 sm:grid-cols-2 lg:grid-cols-4"
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
            class="sm:col-span-2 lg:col-span-2"
          />
        </div>
      </div>
    </div>
    <div
      v-else
      class="rounded-xl border border-dashed border-outline-gray-2 bg-surface-elevation-1 px-4 py-7 text-center text-sm text-ink-gray-5"
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

const servicePalette = {
  'DTF Printing': { tone: 'violet', accent: '#8b7cf6', glow: '#8b7cf61f' },
  'Artwork Preparation': {
    tone: 'amber',
    accent: '#f2b653',
    glow: '#f2b6531f',
  },
  Embroidery: { tone: 'cyan', accent: '#4fc3e8', glow: '#4fc3e81f' },
  'Screen Printing': {
    tone: 'green',
    accent: '#4fd19f',
    glow: '#4fd19f1f',
  },
  Sublimation: { tone: 'pink', accent: '#e875b5', glow: '#e875b51f' },
  'Heat Transfer Printing': {
    tone: 'orange',
    accent: '#ef9851',
    glow: '#ef98511f',
  },
  Combined: { tone: 'purple', accent: '#b07bea', glow: '#b07bea1f' },
}
const defaultServicePalette = {
  tone: 'gray',
  accent: '#999999',
  glow: '#99999918',
}

function placementLabel(value) {
  return (
    placementOptions.find((option) => option.value === value)?.label || value
  )
}

function serviceAppearance(row) {
  return servicePalette[row.production_type] || defaultServicePalette
}

function serviceTone(row) {
  return serviceAppearance(row).tone
}

function serviceCardStyle(row) {
  const appearance = serviceAppearance(row)
  return {
    '--service-accent': appearance.accent,
    '--service-glow': appearance.glow,
    borderLeftColor: appearance.accent,
  }
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

watch(rows, clearLegacyZeroDimensions, { immediate: true })
</script>

<style scoped>
@import './orderEditor.css';

.order-service-card {
  background:
    linear-gradient(135deg, var(--service-glow), transparent 34%),
    rgb(var(--surface-elevation-1));
  box-shadow: 0 10px 28px rgb(0 0 0 / 0.07);
}

.order-service-header {
  background: linear-gradient(90deg, var(--service-glow), transparent 68%);
}
</style>
