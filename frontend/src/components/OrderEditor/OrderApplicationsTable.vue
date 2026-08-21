<!-- eslint-disable vue/no-mutating-props -->
<template>
  <div class="mb-5">
    <div class="mb-2 flex items-center justify-between">
      <h3 class="font-medium">{{ __('Applications') }}</h3>
      <Button
        :label="__('Add application')"
        :disabled="!items.length"
        @click="add"
      />
    </div>
    <p v-if="!items.length" class="mb-2 text-sm text-ink-gray-5">
      {{ __('Add an item before adding an application.') }}
    </p>
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr>
            <th>{{ __('Item') }}</th>
            <th>{{ __('Production') }}</th>
            <th>{{ __('Placement') }}</th>
            <th>{{ __('Qty') }}</th>
            <th>{{ __('Rate') }}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in rows" :key="row.name || index">
            <td>
              <select v-model="row.item_key" class="input">
                <option
                  v-for="item in items"
                  :key="item.item_key"
                  :value="item.item_key"
                >
                  {{ item.item_name || item.item_key }}
                </option>
              </select>
            </td>
            <td>
              <select v-model="row.production_type" class="input">
                <option v-for="type in productionTypes" :key="type">
                  {{ type }}
                </option>
              </select>
            </td>
            <td>
              <select v-model="row.placement" class="input">
                <option v-for="place in placements" :key="place">
                  {{ place }}
                </option>
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
                v-model.number="row.rate"
                type="number"
                min="0"
                class="input"
              />
            </td>
            <td>
              <Button
                :label="__('Remove')"
                theme="red"
                @click="rows.splice(index, 1)"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import { Button } from 'frappe-ui'
const props = defineProps({ doc: { type: Object, required: true } })
const rows = computed(() => props.doc.order_applications || [])
const items = computed(() => props.doc.order_items || [])
const productionTypes = [
  'DTF Printing',
  'Screen Printing',
  'Embroidery',
  'Sublimation',
  'Heat Transfer Printing',
  'Combined',
]
const placements = ['Chest', 'Back', 'Sleeve', 'Tag / Inner Part', 'Other']
function add() {
  rows.value.push({
    item_key: items.value[0].item_key,
    production_type: 'DTF Printing',
    placement: 'Chest',
    qty: 1,
    rate: 0,
  })
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
