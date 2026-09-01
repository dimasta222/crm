<template>
  <SettingsLayoutBase
    :title="__('Tracking Links')"
    :description="__(
      'Create manager-specific links for the website, maps, messengers, and QR codes.',
    )"
  >
    <template #header-actions>
      <Button
        :label="__('New Tracking Link')"
        icon-left="plus"
        variant="solid"
        @click="openForm()"
      />
    </template>
    <template #content>
      <div v-if="links.list.loading" class="flex justify-center py-16">
        <LoadingIndicator class="size-6" />
      </div>
      <EmptyState
        v-else-if="!links.data?.length"
        :title="__('No Tracking Links Found')"
        :description="__('Add a link to start recording who attracted each lead.')"
        icon="link"
      />
      <div v-else>
        <div
          class="grid grid-cols-[2fr_1fr_1.4fr_0.7fr_0.7fr_5rem] gap-3 px-3 py-2 text-sm text-ink-gray-5"
        >
          <div>{{ __('Title') }}</div>
          <div>{{ __('Channel') }}</div>
          <div>{{ __('Attracted By') }}</div>
          <div>{{ __('Clicks') }}</div>
          <div>{{ __('Leads') }}</div>
          <div />
        </div>
        <hr class="border-outline-gray-2" />
        <div
          v-for="link in links.data"
          :key="link.name"
          class="grid grid-cols-[2fr_1fr_1.4fr_0.7fr_0.7fr_5rem] items-center gap-3 rounded px-3 py-3 hover:bg-surface-sidebar"
        >
          <button class="min-w-0 text-left" @click="openForm(link)">
            <div class="truncate font-medium text-ink-gray-8">
              {{ link.title }}
            </div>
            <div class="truncate text-sm text-ink-gray-5">
              {{ trackingUrl(link.tracking_code) }}
            </div>
          </button>
          <div class="truncate">{{ __(link.channel) }}</div>
          <div class="truncate">{{ link.manager }}</div>
          <div>{{ link.click_count || 0 }}</div>
          <div>{{ leadCount(link.tracking_code) }}</div>
          <div class="flex justify-end gap-1">
            <Button
              icon="copy"
              variant="ghost"
              :tooltip="__('Copy Link')"
              @click="copyLink(link)"
            />
            <Dropdown :options="rowActions(link)" placement="right">
              <Button icon="more-horizontal" variant="ghost" />
            </Dropdown>
          </div>
        </div>
      </div>
    </template>
  </SettingsLayoutBase>

  <Dialog
    v-model="dialog"
    :options="{ title: editingName ? __('Edit Tracking Link') : __('New Tracking Link') }"
  >
    <template #body-content>
      <div class="grid grid-cols-2 gap-4">
        <FormControl
          v-model="form.title"
          :label="__('Title')"
          :placeholder="__('Website — manager name')"
          class="col-span-2"
        />
        <FormControl
          v-model="form.tracking_code"
          :label="__('Tracking Code')"
          :placeholder="__('Generated automatically')"
          :disabled="Boolean(editingName)"
        />
        <FormControl
          v-model="form.channel"
          type="select"
          :label="__('Channel')"
          :options="channels"
        />
        <Link v-model="form.manager" doctype="User" :label="__('Attracted By')" />
        <Link
          v-model="form.source"
          doctype="CRM Lead Source"
          :label="__('Source')"
        />
        <FormControl
          v-model="form.campaign_name"
          :label="__('Campaign')"
          class="col-span-2"
        />
        <FormControl
          v-model="form.destination_url"
          :label="__('Destination URL')"
          placeholder="https://..."
          class="col-span-2"
        />
        <FormControl
          v-if="form.channel === 'Telegram'"
          v-model="form.telegram_bot_username"
          :label="__('Telegram Bot Username')"
          placeholder="my_company_bot"
          class="col-span-2"
        />
        <div class="col-span-2 flex items-center justify-between">
          <span class="text-sm text-ink-gray-7">{{ __('Active') }}</span>
          <Switch v-model="form.active" />
        </div>
        <ErrorMessage v-if="error" :message="error" class="col-span-2" />
      </div>
    </template>
    <template #actions>
      <Button
        class="w-full"
        variant="solid"
        :label="__('Save')"
        :loading="links.insert.loading || links.setValue.loading"
        @click="save"
      />
    </template>
  </Dialog>
</template>

<script setup>
import EmptyState from '@/components/ListViews/EmptyState.vue'
import SettingsLayoutBase from '@/components/Layouts/SettingsLayoutBase.vue'
import Link from '@/components/Controls/Link.vue'
import {
  Dialog,
  Dropdown,
  ErrorMessage,
  FormControl,
  LoadingIndicator,
  Switch,
  createResource,
  createListResource,
  toast,
} from 'frappe-ui'
import { reactive, ref } from 'vue'

const channels = [
  'Website',
  'Yandex Maps',
  'Telegram',
  'Avito',
  'MAX',
  'QR Code',
  'Other',
]

const links = createListResource({
  type: 'list',
  doctype: 'CRM Tracking Link',
  cache: 'crm_tracking_links',
  fields: [
    'name',
    'title',
    'tracking_code',
    'destination_url',
    'active',
    'manager',
    'source',
    'channel',
    'campaign_name',
    'telegram_bot_username',
    'click_count',
    'last_clicked_at',
  ],
  auto: true,
  orderBy: 'modified desc',
  pageLength: 100,
})

const attribution = createResource({
  url: 'crm.api.attribution.get_attribution_summary',
  auto: true,
})

function leadCount(trackingCode) {
  return (attribution.data || [])
    .filter((row) => row.tracking_code === trackingCode)
    .reduce((total, row) => total + Number(row.lead_count || 0), 0)
}

const blankForm = () => ({
  title: '',
  tracking_code: '',
  destination_url: '',
  active: true,
  manager: '',
  source: '',
  channel: 'Website',
  campaign_name: '',
  telegram_bot_username: '',
})

const dialog = ref(false)
const editingName = ref('')
const error = ref('')
const form = reactive(blankForm())

function openForm(link = null) {
  Object.assign(form, blankForm(), link || {})
  editingName.value = link?.name || ''
  error.value = ''
  dialog.value = true
}

function save() {
  if (!form.title || !form.manager || !form.channel || !form.destination_url) {
    error.value = __('Fill in all required fields.')
    return
  }
  const values = { ...form, active: form.active ? 1 : 0 }
  const options = {
    onSuccess: () => {
      dialog.value = false
      links.reload()
      toast.success(__('Tracking link saved successfully'))
    },
    onError: (response) => {
      error.value = response.messages?.[0] || response.message
    },
  }
  if (editingName.value) {
    links.setValue.submit({ name: editingName.value, ...values }, options)
  } else {
    links.insert.submit(values, options)
  }
}

function trackingUrl(code) {
  return `${window.location.origin}/track?code=${code}`
}

async function copyLink(link) {
  await navigator.clipboard.writeText(trackingUrl(link.tracking_code))
  toast.success(__('Link copied'))
}

function rowActions(link) {
  return [
    { label: __('Edit'), icon: 'edit', onClick: () => openForm(link) },
    {
      label: __('Delete'),
      icon: 'trash-2',
      theme: 'red',
      onClick: () =>
        links.delete.submit(link.name, {
          onSuccess: () => toast.success(__('Tracking link deleted')),
          onError: (response) =>
            toast.error(response.messages?.[0] || response.message),
        }),
    },
  ]
}
</script>
