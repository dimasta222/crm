<!-- eslint-disable vue/no-mutating-props -->
<template>
  <Section
    :label="__('DTF Pieces')"
    :collapsible="false"
    label-class="font-medium"
  >
    <template #actions>
      <Button
        :label="__('Add position')"
        icon-left="plus"
        size="sm"
        variant="subtle"
        @click="add"
      />
    </template>

    <div class="order-grid mt-2 overflow-x-auto">
      <table class="w-full min-w-[720px] text-sm">
        <thead>
          <tr>
            <th>{{ __('Sizing') }}</th>
            <th>{{ __('Size') }}</th>
            <th class="w-24 text-right">{{ __('Qty') }}</th>
            <th class="w-28 text-right">{{ __('Unit price') }}</th>
            <th class="w-32 text-right">{{ __('Amount') }}</th>
            <th class="w-10" />
          </tr>
        </thead>
        <tbody v-if="rows.length">
          <tr v-for="(row, index) in rows" :key="row.name || index">
            <td class="min-w-40">
              <Select
                v-model="row.sizing_mode"
                :options="sizingOptions"
                :placeholder="__('Select option')"
              />
            </td>
            <td class="min-w-40">
              <Select
                v-if="row.sizing_mode === 'Format'"
                v-model="row.sheet_format"
                :options="sheetFormatOptions"
                :placeholder="__('Select option')"
              />
              <div
                v-else-if="row.sizing_mode === 'Custom Size'"
                class="flex gap-1"
              >
                <FormControl
                  v-model="row.width_cm"
                  type="number"
                  min="0"
                  :placeholder="__('Width')"
                />
                <FormControl
                  v-model="row.height_cm"
                  type="number"
                  min="0"
                  :placeholder="__('Height')"
                />
              </div>
              <span v-else class="text-ink-gray-5">{{ __('—') }}</span>
            </td>
            <td><FormControl v-model="row.qty" type="number" min="0" /></td>
            <td>
              <FormControl v-model="row.unit_price" type="number" min="0" />
            </td>
            <td>
              <FormControl
                v-model="row.manual_amount"
                type="number"
                min="0"
                @input="row.use_manual_amount = 1"
              />
              <Checkbox
                v-model="row.use_manual_amount"
                class="mt-1"
                :label="__('Set amount manually')"
              />
            </td>
            <td>
              <Button
                :tooltip="__('Delete row')"
                icon="trash-2"
                size="sm"
                variant="ghost"
                @click="rows.splice(index, 1)"
              />
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!rows.length" class="order-grid-empty">
        {{ __('No positions added') }}
      </div>
    </div>
  </Section>
</template>

<script setup>
import Section from '@/components/Section.vue'
import { computed } from 'vue'
import { Button, Checkbox, FormControl, Select } from 'frappe-ui'
import { SHEET_FORMATS } from '@/utils/orderEditor'

const props = defineProps({ doc: { type: Object, required: true } })
const rows = computed(() => props.doc.dtf_piece_lines || [])
const sizingOptions = [
  { label: __('Format'), value: 'Format' },
  { label: __('Custom Size'), value: 'Custom Size' },
  { label: __('Quantity Only'), value: 'Quantity Only' },
]
const sheetFormatOptions = SHEET_FORMATS.map((value) => ({
  label: value,
  value,
}))
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
@import './orderEditor.css';
</style>
