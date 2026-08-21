<!-- eslint-disable vue/no-mutating-props -->
<template>
  <div class="mb-5">
    <div class="mb-2 flex items-center justify-between">
      <h3 class="font-medium">{{ __('Items') }}</h3>
      <Button :label="__('Add item')" @click="add" />
    </div>
    <p v-if="blockedRemoval" class="mb-2 text-sm text-ink-amber-3">
      {{
        __(
          'This item has applications and cannot be removed until they are removed or reassigned.',
        )
      }}
    </p>
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr>
            <th>{{ __('Name / Product') }}</th>
            <th>{{ __('Supply') }}</th>
            <th>{{ __('Qty') }}</th>
            <th>{{ __('Rate') }}</th>
            <th>{{ __('Discount %') }}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, index) in rows"
            :key="row.name || row.item_key || index"
          >
            <td>
              <input
                v-model="row.item_name"
                :placeholder="__('Item name')"
                class="input"
              />
              <Link
                v-if="row.supply_type === 'Studio Product'"
                :model-value="row.product"
                doctype="CRM Product"
                :placeholder="__('CRM Product')"
                class="input mt-1"
                @update:model-value="
                  (product) => onStudioProductChange(row, product)
                "
              />
              <p
                v-if="studioProductErrors[rowKey(row)]"
                class="mt-1 text-xs text-ink-red-3"
                role="alert"
              >
                {{ studioProductErrors[rowKey(row)] }}
              </p>
            </td>
            <td>
              <select v-model="row.supply_type" class="input">
                <option>Customer Item</option>
                <option>Studio Product</option>
              </select>
            </td>
            <td>
              <input
                v-model.number="row.qty"
                type="number"
                min="0"
                class="input"
              />
            </td>
            <td>
              <input
                v-model.number="row.manual_rate"
                type="number"
                min="0"
                class="input"
                @input="row.use_manual_rate = 1"
              /><label class="text-xs"
                ><input v-model="row.use_manual_rate" type="checkbox" />
                {{ __('Manual') }}</label
              >
            </td>
            <td>
              <input
                v-model.number="row.discount_percentage"
                type="number"
                min="0"
                max="100"
                class="input"
              />
            </td>
            <td>
              <Button
                :label="__('Remove')"
                theme="red"
                @click="remove(index)"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<script setup>
import { computed, reactive, ref } from 'vue'
import { Button, createResource } from 'frappe-ui'
import Link from '@/components/Controls/Link.vue'
import { canRemoveOrderItem, selectStudioProduct } from '@/utils/orderEditor'
const props = defineProps({ doc: { type: Object, required: true } })
const rows = computed(() => props.doc.order_items || [])
const blockedRemoval = ref(false)
const studioProductErrors = reactive({})
const rowKey = (row) => row.name || row.item_key

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
    studioProductErrors[key] = __(
      'The selected CRM Product has no Standard Rate.',
    )
  } else if (result.error === 'load-failed') {
    studioProductErrors[key] = __(
      'Unable to load the selected CRM Product rate.',
    )
  }
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
.input {
  @apply w-full rounded border border-outline-gray-2 px-2 py-1;
}
th,
td {
  @apply p-1 text-left align-top;
}
</style>
