<template>
  <div class="h-full w-full">
    <div
      v-if="item.type == 'number_chart'"
      class="flex h-full w-full cursor-pointer overflow-hidden rounded shadow"
    >
      <Tooltip :text="__(item.data.tooltip)">
        <NumberChart
          v-if="item.data"
          :key="index"
          class="!items-start"
          :config="item.data"
        >
          <template v-if="isDashboardCurrencyCard(item.name)" #subtitle>
            <div
              class="max-h-[72px] w-full max-w-full overflow-auto break-all font-semibold leading-tight text-ink-gray-9"
              :class="getDashboardCurrencyValueClass(currencyValue(item.data))"
              :title="currencyValue(item.data)"
              data-testid="dashboard-currency-value"
            >
              {{ currencyValue(item.data) }}
            </div>
          </template>
        </NumberChart>
      </Tooltip>
    </div>
    <div
      v-else-if="item.type == 'spacer'"
      class="rounded bg-surface-base h-full overflow-hidden text-ink-gray-5 flex items-center justify-center"
      :class="editing ? 'border border-dashed border-outline-gray-2' : ''"
    >
      {{ editing ? __('Spacer') : '' }}
    </div>
    <div
      v-else-if="item.type == 'axis_chart'"
      class="h-full w-full rounded-md bg-surface-base shadow"
    >
      <AxisChart v-if="item.data" :config="getDashboardChartConfig(item)" />
    </div>
    <div
      v-else-if="item.type == 'donut_chart'"
      class="h-full w-full rounded-md bg-surface-base shadow overflow-hidden"
    >
      <DonutChart v-if="item.data" :config="item.data" />
    </div>
  </div>
</template>
<script setup>
import { AxisChart, DonutChart, NumberChart, Tooltip } from 'frappe-ui'
import {
  formatDashboardCurrency,
  getDashboardChartConfig,
  getDashboardCurrencyValueClass,
  isDashboardCurrencyCard,
} from '@/utils/dashboard'

defineProps({
  index: { type: Number, required: true },
  item: { type: Object, required: true },
  editing: { type: Boolean, default: false },
})

function currencyValue(config) {
  return formatDashboardCurrency(config.value, config.prefix)
}
</script>
