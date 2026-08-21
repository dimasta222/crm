<!-- eslint-disable vue/no-mutating-props -->
<template>
  <div class="mb-5">
    <div class="mb-2 flex items-center justify-between">
      <h3 class="font-medium">{{ __('DTF Rolls') }}</h3>
      <Button :label="__('Add roll')" @click="add" />
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr>
            <th>{{ __('Length (m)') }}</th>
            <th>{{ __('Rate per Meter') }}</th>
            <th>{{ __('Manual amount') }}</th>
            <th>{{ __('Comment') }}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in rows" :key="row.name || index">
            <td>
              <input
                v-model.number="row.length_m"
                type="number"
                min="0"
                class="input"
              />
            </td>
            <td>
              <input
                v-model.number="row.rate_per_meter"
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
            <td><input v-model="row.comment" class="input" /></td>
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
const rows = computed(() => props.doc.dtf_roll_lines || [])
function add() {
  rows.value.push({ length_m: 1, rate_per_meter: 0 })
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
