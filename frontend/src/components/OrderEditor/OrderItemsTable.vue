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
    <div class="order-grid mt-2 overflow-x-auto">
      <table class="w-full min-w-[760px] text-sm">
        <thead>
          <tr>
            <th>{{ __('Name / Product') }}</th>
            <th>{{ __('Supply') }}</th>
            <th class="w-24 text-right">{{ __('Qty') }}</th>
            <th class="w-32 text-right">{{ __('Rate') }}</th>
            <th class="w-28 text-right">{{ __('Discount %') }}</th>
            <th class="w-10" />
          </tr>
        </thead>
        <tbody v-if="rows.length">
          <tr
            v-for="(row, index) in rows"
            :key="row.name || row.item_key || index"
          >
            <td class="min-w-52">
              <FormControl
                v-model="row.item_name"
                type="text"
                :placeholder="__('Item name')"
              />
              <Link
                v-if="row.supply_type === 'Studio Product'"
                v-model="row.product"
                doctype="CRM Product"
                :placeholder="__('Select CRM Product')"
                class="mt-1"
                @update:model-value="
                  (product) => onStudioProductChange(row, product)
                "
              />
              <div
                v-if="row.supply_type === 'Studio Product'"
                class="mt-1 flex flex-wrap gap-1"
              >
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
              <p
                v-if="studioProductErrors[rowKey(row)]"
                class="mt-1 text-xs text-ink-red-3"
                role="alert"
              >
                {{ studioProductErrors[rowKey(row)] }}
              </p>
            </td>
            <td class="min-w-40">
              <Select
                v-model="row.supply_type"
                :options="supplyOptions"
                :placeholder="__('Select option')"
              />
            </td>
            <td><FormControl v-model="row.qty" type="number" min="0" /></td>
            <td>
              <FormControl
                v-model="row.manual_rate"
                type="number"
                min="0"
                @input="row.use_manual_rate = 1"
              />
              <Checkbox
                v-model="row.use_manual_rate"
                class="mt-1"
                :label="__('Set rate manually')"
              />
            </td>
            <td>
              <FormControl
                v-model="row.discount_percentage"
                type="number"
                min="0"
                max="100"
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
        </tbody>
      </table>
      <div v-if="!rows.length" class="order-grid-empty">
        {{ __('No items added') }}
      </div>
    </div>
  </Section>
</template>

<script setup>
import Section from '@/components/Section.vue'
import Link from '@/components/Controls/Link.vue'
import { createDocument } from '@/composables/document'
import { useDoctypeModal } from '@/composables/doctypeModal'
import { computed, reactive, ref } from 'vue'
import {
  Button,
  Checkbox,
  createResource,
  FormControl,
  Select,
} from 'frappe-ui'
import { canRemoveOrderItem, selectStudioProduct } from '@/utils/orderEditor'

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

async function onStudioProductChange(row, product) {
  const key = rowKey(row)
  delete studioProductErrors[key]
  const result = await selectStudioProduct(row, product, (name) =>
    createResource({
      url: 'frappe.client.get',
      params: { doctype: 'CRM Product', name },
    }).fetch(),
  )
  if (result.error === 'missing-standard-rate') {
    studioProductErrors[key] = __('The selected product has no standard rate.')
  } else if (result.error === 'load-failed') {
    studioProductErrors[key] = __('Unable to load the product rate.')
  }
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
</script>

<style scoped>
@import './orderEditor.css';
</style>
