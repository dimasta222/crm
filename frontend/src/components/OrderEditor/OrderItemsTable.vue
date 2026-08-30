<!-- eslint-disable vue/no-mutating-props -->
<template>
  <Section :label="__('Items')" :collapsible="false" label-class="font-medium">
    <template #actions>
      <Button
        :label="__('Add item')"
        icon-left="plus"
        size="sm"
        variant="subtle"
        @click="add"
      />
    </template>

    <p v-if="blockedRemoval" class="mb-2 mt-2 text-sm text-ink-amber-3">
      {{
        __(
          'This item has applications. Remove or reassign them before deleting the item.',
        )
      }}
    </p>

    <div v-if="rows.length" class="mt-2 space-y-3">
      <div
        v-for="(row, index) in rows"
        :key="row.name || row.item_key || index"
        data-testid="order-item-group"
        :data-item-key="row.item_key"
        class="overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-white"
      >
        <div
          class="border-b border-outline-gray-2 bg-surface-gray-1 px-4 py-3"
        >
          <div class="mb-3 flex flex-wrap items-start justify-between gap-3">
            <div>
              <div class="text-sm font-medium text-ink-gray-8">
                {{ __('Item') }} №{{ index + 1 }} ·
                {{ row.item_name || __('Item name') }}
              </div>
            </div>
            <Button
              :tooltip="__('Delete row')"
              icon="trash-2"
              size="sm"
              variant="ghost"
              @click="remove(index)"
            />
          </div>

          <div
            class="grid grid-cols-1 items-start gap-3 sm:grid-cols-2 lg:grid-cols-6"
          >
            <div class="min-w-0">
              <div class="mb-1 h-4 whitespace-nowrap text-xs text-ink-gray-5">
                {{ __('Supply') }}
              </div>
              <Select
                v-model="row.supply_type"
                :options="supplyOptions"
                :placeholder="__('Select option')"
                @update:model-value="
                  (supplyType) => onSupplyTypeChange(row, supplyType)
                "
              />
            </div>
            <FormControl
              v-model="row.item_name"
              type="text"
              :label="__('Name / Product')"
              :placeholder="__('Item name')"
              class="lg:col-span-2"
            />
            <FormControl
              v-model="row.qty"
              type="number"
              min="0"
              :label="__('Qty')"
            />
            <FormControl
              v-if="row.supply_type === 'Studio Product'"
              v-model="row.manual_rate"
              type="number"
              min="0"
              step="0.01"
              :label="__('Rate')"
              @input="row.use_manual_rate = 1"
            />
            <FormControl
              v-if="row.supply_type === 'Studio Product'"
              v-model="row.discount_percentage"
              type="number"
              min="0"
              max="100"
              :label="__('Discount %')"
            />
            <div v-else class="min-w-0">
              <div class="mb-1 h-4 whitespace-nowrap text-xs text-ink-gray-5">
                {{ __('Rate') }}
              </div>
              <div
                class="flex h-8 items-center rounded border border-outline-gray-2 bg-surface-white px-2 text-sm text-ink-gray-5"
              >
                {{ __('Not charged') }}
              </div>
            </div>
          </div>

          <div
            v-if="row.supply_type === 'Studio Product'"
            class="mt-3 grid grid-cols-1 items-start gap-3 sm:grid-cols-2"
          >
            <div class="min-w-0">
              <div class="mb-1 h-4 whitespace-nowrap text-xs text-ink-gray-5">
                {{ __('Name / Product') }}
              </div>
              <Link
                v-model="row.product"
                doctype="CRM Product"
                :selected-label="row.item_name"
                :placeholder="__('Select CRM Product')"
                @update:model-value="
                  (product) => onStudioProductChange(row, product)
                "
              />
            </div>
            <div class="flex h-full flex-wrap items-end gap-1">
              <Button
                :label="__('Create product')"
                icon-left="plus"
                size="sm"
                variant="ghost"
                @click="createStudioProduct(row)"
              />
              <Button
                :label="__('Open product')"
                icon-left="external-link"
                size="sm"
                variant="ghost"
                :disabled="!row.product"
                @click="openStudioProduct(row)"
              />
            </div>
          </div>
          <p
            v-if="studioProductErrors[rowKey(row)]"
            class="mt-2 text-xs text-ink-red-3"
            role="alert"
          >
            {{ studioProductErrors[rowKey(row)] }}
          </p>
        </div>

        <OrderApplicationsTable :doc="doc" :item-key="row.item_key" />
        <div
          class="flex items-center justify-between gap-3 border-t border-outline-gray-2 bg-surface-gray-1 px-4 py-3 text-sm"
        >
          <span class="text-ink-gray-6">{{ __('Total') }}</span>
          <span class="font-medium text-ink-gray-8">
            {{ formatAmount(groupAmount(row)) }}
          </span>
        </div>
      </div>
    </div>
    <div v-else class="order-grid-empty mt-2">
      {{ __('No items added') }}
    </div>
  </Section>
</template>

<script setup>
import Section from '@/components/Section.vue'
import Link from '@/components/Controls/Link.vue'
import { createDocument } from '@/composables/document'
import { useDoctypeModal } from '@/composables/doctypeModal'
import { getMeta } from '@/stores/meta'
import { computed, onMounted, reactive, ref } from 'vue'
import { Button, createResource, FormControl, Select } from 'frappe-ui'
import {
  calculateOrderPreview,
  canRemoveOrderItem,
  getOrderCurrencyPrecision,
  selectStudioProduct,
} from '@/utils/orderEditor'
import OrderApplicationsTable from './OrderApplicationsTable.vue'

const props = defineProps({ doc: { type: Object, required: true } })
const rows = computed(() => props.doc.order_items || [])
const blockedRemoval = ref(false)
const studioProductErrors = reactive({})
const supplyOptions = [
  { label: __('Customer Item'), value: 'Customer Item' },
  { label: __('Studio Product'), value: 'Studio Product' },
]
const rowKey = (row) => row.name || row.item_key
const { showModal } = useDoctypeModal()
const { doctypeMeta } = getMeta('CRM Deal')
const precision = computed(() =>
  getOrderCurrencyPrecision(
    doctypeMeta.value?.fields?.find(
      (field) => field.fieldname === 'order_total',
    ),
    window.sysdefaults,
  ),
)

function groupAmount(row) {
  return calculateOrderPreview(
    {
      order_items: [row],
      order_applications: (props.doc.order_applications || []).filter(
        (application) => application.item_key === row.item_key,
      ),
    },
    precision.value,
  ).orderTotal
}

function formatAmount(value) {
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: props.doc.currency || 'RUB',
    minimumFractionDigits: precision.value,
    maximumFractionDigits: precision.value,
  }).format(value)
}

function getStudioProduct(name) {
  return createResource({
    url: 'frappe.client.get',
    params: { doctype: 'CRM Product', name },
  }).fetch()
}

async function hydrateStudioProductName(row) {
  const product = row.product
  if (!product || row.supply_type !== 'Studio Product') return
  try {
    const selectedProduct = await getStudioProduct(product)
    if (row.product !== product) return
    row.item_name =
      selectedProduct?.product_name || selectedProduct?.name || product
    if (!row.use_manual_rate) {
      row.manual_rate =
        row.rate ?? row.base_rate ?? selectedProduct?.standard_rate
      row.use_manual_rate = 1
    }
  } catch {
    // A failed label lookup must not block editing an existing order.
  }
}

async function onStudioProductChange(row, product) {
  const key = rowKey(row)
  delete studioProductErrors[key]
  const result = await selectStudioProduct(row, product, getStudioProduct)
  if (result.error === 'missing-standard-rate') {
    studioProductErrors[key] = __('The selected product has no standard rate.')
  } else if (result.error === 'load-failed') {
    studioProductErrors[key] = __('Unable to load the product rate.')
  }
}

function onSupplyTypeChange(row, supplyType) {
  row.supply_type = supplyType
  if (supplyType !== 'Customer Item') return
  row.product = null
  row.base_rate = 0
  row.manual_rate = 0
  row.rate = 0
  row.use_manual_rate = 0
  row.discount_percentage = 0
}

function createStudioProduct(row) {
  const key = rowKey(row)
  delete studioProductErrors[key]
  createDocument('CRM Product', {}, null, async (product) => {
    if (!product?.name) {
      studioProductErrors[key] = __('Unable to create the product.')
      return
    }
    await onStudioProductChange(row, product.name)
  })
}

function openStudioProduct(row) {
  if (!row.product) return
  showModal({
    name: row.product,
    doctype: 'CRM Product',
    title: __('Product'),
    callbacks: {
      afterUpdate: async (product) => {
        await onStudioProductChange(row, product?.name || row.product)
      },
    },
  })
}

function add() {
  rows.value.push({
    item_key: `item-${Date.now()}`,
    supply_type: 'Customer Item',
    qty: 1,
    discount_percentage: 0,
  })
}

function remove(index) {
  const key = rows.value[index].item_key
  if (!canRemoveOrderItem(props.doc, key)) {
    blockedRemoval.value = true
    return
  }
  blockedRemoval.value = false
  rows.value.splice(index, 1)
}

onMounted(() => {
  rows.value.forEach((row) => hydrateStudioProductName(row))
})
</script>

<style scoped>
@import './orderEditor.css';
</style>
