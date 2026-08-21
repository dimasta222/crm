<!-- eslint-disable vue/no-mutating-props -->
<template>
  <Section
    :label="__('DTF Roll')"
    :collapsible="false"
    label-class="font-medium"
  >
    <template #actions>
      <Button
        :label="__('Add roll')"
        icon-left="plus"
        size="sm"
        variant="subtle"
        @click="add"
      />
    </template>

    <div class="order-grid mt-2 overflow-x-auto">
      <table class="w-full min-w-[640px] text-sm">
        <thead>
          <tr>
            <th class="text-right">{{ __('Length (m)') }}</th>
            <th class="text-right">{{ __('Rate per meter') }}</th>
            <th class="text-right">{{ __('Amount') }}</th>
            <th>{{ __('Comment') }}</th>
            <th class="w-10" />
          </tr>
        </thead>
        <tbody v-if="rows.length">
          <tr v-for="(row, index) in rows" :key="row.name || index">
            <td>
              <FormControl v-model="row.length_m" type="number" min="0" />
            </td>
            <td>
              <FormControl v-model="row.rate_per_meter" type="number" min="0" />
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
              <FormControl
                v-model="row.comment"
                type="text"
                :placeholder="__('Comment')"
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
        {{ __('No rolls added') }}
      </div>
    </div>
  </Section>
</template>

<script setup>
import Section from '@/components/Section.vue'
import { computed } from 'vue'
import { Button, Checkbox, FormControl } from 'frappe-ui'

const props = defineProps({ doc: { type: Object, required: true } })
const rows = computed(() => props.doc.dtf_roll_lines || [])
function add() {
  rows.value.push({ length_m: 1, rate_per_meter: 0 })
}
</script>

<style scoped>
@import './orderEditor.css';
</style>
