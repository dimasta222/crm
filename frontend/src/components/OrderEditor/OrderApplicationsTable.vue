<!-- eslint-disable vue/no-mutating-props -->
<template>
  <Section
    :label="__('Services and applications')"
    :collapsible="false"
    label-class="font-medium"
  >
    <template #actions>
      <Button
        :label="__('Add service')"
        icon-left="plus"
        size="sm"
        variant="subtle"
        :disabled="!items.length"
        @click="add"
      />
    </template>

    <div class="order-grid mt-2 overflow-x-auto">
      <table class="w-full min-w-[880px] text-sm">
        <thead>
          <tr>
            <th>{{ __('Item') }}</th>
            <th>{{ __('Production type') }}</th>
            <th>{{ __('Placement') }}</th>
            <th class="w-24 text-right">{{ __('Qty') }}</th>
            <th class="w-28 text-right">{{ __('Rate') }}</th>
            <th class="w-28 text-right">{{ __('Amount') }}</th>
            <th class="w-24" />
            <th class="w-10" />
          </tr>
        </thead>
        <tbody v-if="rows.length">
          <template
            v-for="(row, index) in rows"
            :key="rowKey(row, index)"
          >
            <tr>
              <td class="min-w-40">
                <Select
                  v-model="row.item_key"
                  :options="itemOptions"
                  :placeholder="__('Select option')"
                />
              </td>
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
                <FormControl
                  v-if="row.production_type !== 'Embroidery'"
                  v-model="row.rate"
                  type="number"
                  min="0"
                />
                <span v-else class="px-2 text-sm text-ink-gray-7">
                  {{ __('By stitches') }}
                </span>
              </td>
              <td class="text-right font-medium text-ink-gray-8">
                {{ formatAmount(calculateApplicationAmount(row, precision)) }}
              </td>
              <td>
                <Button
                  :label="__('Parameters')"
                  size="sm"
                  variant="ghost"
                  @click="toggleDetails(row, index)"
                />
              </td>
              <td>
                <Button
                  :tooltip="__('Delete row')"
                  icon="trash-2"
                  size="sm"
                  variant="ghost"
                  @click="remove(index)"
                />
              </td>
            </tr>
            <tr v-if="detailsOpen[rowKey(row, index)]">
              <td colspan="8" class="!p-3">
                <div
                  class="grid grid-cols-1 gap-3 rounded-md bg-surface-gray-1 p-3 sm:grid-cols-2 lg:grid-cols-4"
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
                    v-model="row.stitch_count"
                    type="number"
                    min="0"
                    :label="__('Stitch count')"
                    :placeholder="__('Full stitch count')"
                  />
                  <FormControl
                    v-if="row.production_type === 'Embroidery'"
                    v-model="row.stitch_rate_per_1000"
                    type="number"
                    min="0"
                    :label="__('Rate per 1,000 stitches')"
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
                  <div
                    v-if="row.production_type === 'Screen Printing'"
                  >
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
      <div v-if="!rows.length" class="order-grid-empty">
        {{
          items.length
            ? __('No applications added')
            : __('Add an item before adding an application')
        }}
      </div>
    </div>
  </Section>
</template>

<script setup>
import Section from '@/components/Section.vue'
import { computed, reactive } from 'vue'
import { Button, FormControl, Select } from 'frappe-ui'
import { getMeta } from '@/stores/meta'
import {
  calculateApplicationAmount,
  getOrderCurrencyPrecision,
} from '@/utils/orderEditor'

const props = defineProps({ doc: { type: Object, required: true } })
const rows = computed(() => props.doc.order_applications || [])
const items = computed(() => props.doc.order_items || [])
const detailsOpen = reactive({})
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
const itemOptions = computed(() =>
  items.value.map((item) => ({
    label: item.item_name || item.product || item.item_key,
    value: item.item_key,
  })),
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
  if (row.production_type === 'Embroidery') {
    row.rate = 0
    if (
      row.stitch_rate_per_1000 == null ||
      row.stitch_rate_per_1000 === ''
    ) {
      row.stitch_rate_per_1000 = 70
    }
  }
}

function toggleDetails(row, index) {
  const key = rowKey(row, index)
  detailsOpen[key] = !detailsOpen[key]
}

function remove(index) {
  delete detailsOpen[rowKey(rows.value[index], index)]
  rows.value.splice(index, 1)
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
  const row = {
    item_key: items.value[0].item_key,
    production_type: 'DTF Printing',
    placement: 'Chest',
    qty: 1,
    rate: 0,
    comment: '',
  }
  rows.value.push(row)
  detailsOpen[rowKey(row, rows.value.length - 1)] = true
}
</script>

<style scoped>
@import './orderEditor.css';
</style>
