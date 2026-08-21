<!-- eslint-disable vue/no-mutating-props -->
<template>
  <Section
    :label="__('Applications')"
    :collapsible="false"
    label-class="font-medium"
  >
    <template #actions>
      <Button
        :label="__('Add application')"
        icon-left="plus"
        size="sm"
        variant="subtle"
        :disabled="!items.length"
        @click="add"
      />
    </template>

    <div class="order-grid mt-2 overflow-x-auto">
      <table class="w-full min-w-[720px] text-sm">
        <thead>
          <tr>
            <th>{{ __('Item') }}</th>
            <th>{{ __('Production type') }}</th>
            <th>{{ __('Placement') }}</th>
            <th class="w-24 text-right">{{ __('Qty') }}</th>
            <th class="w-28 text-right">{{ __('Rate') }}</th>
            <th class="w-10" />
          </tr>
        </thead>
        <tbody v-if="rows.length">
          <tr v-for="(row, index) in rows" :key="row.name || index">
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
              />
            </td>
            <td class="min-w-36">
              <Select
                v-model="row.placement"
                :options="placementOptions"
                :placeholder="__('Select option')"
              />
            </td>
            <td><FormControl v-model="row.qty" type="number" min="0" /></td>
            <td><FormControl v-model="row.rate" type="number" min="0" /></td>
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
import { computed } from 'vue'
import { Button, FormControl, Select } from 'frappe-ui'

const props = defineProps({ doc: { type: Object, required: true } })
const rows = computed(() => props.doc.order_applications || [])
const items = computed(() => props.doc.order_items || [])
const itemOptions = computed(() =>
  items.value.map((item) => ({
    label: item.item_name || item.item_key,
    value: item.item_key,
  })),
)
const productionTypeOptions = [
  'DTF Printing',
  'Screen Printing',
  'Embroidery',
  'Sublimation',
  'Heat Transfer Printing',
  'Combined',
].map((value) => ({ label: __(value), value }))
const placementOptions = [
  { label: __('Chest'), value: 'Chest' },
  { label: __('Back placement'), value: 'Back' },
  { label: __('Sleeve'), value: 'Sleeve' },
  { label: __('Tag / Inner Part'), value: 'Tag / Inner Part' },
  { label: __('Other'), value: 'Other' },
]

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
@import './orderEditor.css';
</style>
