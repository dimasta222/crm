<!-- eslint-disable vue/no-mutating-props -->
<template>
  <div class="mb-5">
    <div class="mb-2 flex items-center justify-between">
      <h3 class="font-medium">{{ __('DTF Pieces') }}</h3>
      <Button :label="__('Add piece')" @click="add" />
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr>
            <th>{{ __('Sizing') }}</th>
            <th>{{ __('Size') }}</th>
            <th>{{ __('Qty') }}</th>
            <th>{{ __('Unit Price') }}</th>
            <th>{{ __('Manual amount') }}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in rows" :key="row.name || index">
            <td>
              <select v-model="row.sizing_mode" class="input">
                <option>Format</option>
                <option>Custom Size</option>
                <option>Quantity Only</option>
              </select>
            </td>
            <td>
              <select
                v-if="row.sizing_mode === 'Format'"
                v-model="row.sheet_format"
                class="input"
              >
                <option v-for="format in SHEET_FORMATS" :key="format">
                  {{ format }}
                </option>
              </select>
              <div
                v-else-if="row.sizing_mode === 'Custom Size'"
                class="flex gap-1"
              >
                <input
                  v-model.number="row.width_cm"
                  type="number"
                  min="0"
                  :placeholder="__('Width')"
                  class="input"
                /><input
                  v-model.number="row.height_cm"
                  type="number"
                  min="0"
                  :placeholder="__('Height')"
                  class="input"
                />
              </div>
              <span v-else class="text-ink-gray-5">{{ __('—') }}</span>
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
                v-model.number="row.unit_price"
                type="number"
                min="0"
                class="input"
              />
            </td>
            <td>
              <input
                v-model.number="row.manual_amount"
                type="number"
                class="input"
                @input="row.use_manual_amount = 1"
              /><label class="text-xs"
                ><input v-model="row.use_manual_amount" type="checkbox" />
                {{ __('Manual') }}</label
              >
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
import { SHEET_FORMATS } from '@/utils/orderEditor'
const props = defineProps({ doc: { type: Object, required: true } })
const rows = computed(() => props.doc.dtf_piece_lines || [])
function add() {
  rows.value.push({
    sizing_mode: 'Format',
    sheet_format: 'A4',
    qty: 1,
    unit_price: 0,
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
