<template>
  <div class="flex flex-col gap-3 px-3 pb-5 sm:px-10">
    <div class="mb-1 flex items-center justify-end">
      <Button
        :label="__('Create channel link code')"
        icon-left="link"
        :loading="creatingCode"
        @click="createHandoff"
      />
    </div>
    <div
      v-if="!messages.length"
      class="flex min-h-64 flex-col items-center justify-center gap-1 text-center"
    >
      <FeatherIcon name="message-circle" class="mb-2 size-8 text-ink-gray-4" />
      <div class="text-lg font-medium text-ink-gray-8">
        {{ __('No Channel Messages Found') }}
      </div>
      <div class="text-p-base text-ink-gray-6">
        {{ __('Messages from connected channels will appear here.') }}
      </div>
    </div>
    <div
      v-for="message in messages"
      :key="message.name"
      class="flex"
      :class="message.direction === 'Outgoing' ? 'justify-end' : 'justify-start'"
    >
      <div
        class="max-w-[85%] rounded-lg border border-outline-gray-2 px-3 py-2 text-base"
        :class="
          message.direction === 'Outgoing'
            ? 'bg-surface-blue-1'
            : 'bg-surface-gray-2'
        "
      >
        <div class="mb-1 flex items-center gap-2 text-sm text-ink-gray-5">
          <span class="font-medium text-ink-gray-8">
            {{ message.sender_name || __(message.direction) }}
          </span>
          <span>{{ __(message.channel) }}</span>
          <Tooltip :text="formatDate(message.sent_at)">
            <span>{{ __(timeAgo(message.sent_at)) }}</span>
          </Tooltip>
        </div>
        <div v-if="message.content" class="whitespace-pre-wrap text-ink-gray-8">
          {{ message.content }}
        </div>
        <a
          v-if="message.attachment_url"
          :href="message.attachment_url"
          target="_blank"
          rel="noopener noreferrer"
          class="mt-2 flex items-center gap-1 text-ink-blue-4 hover:underline"
        >
          <FeatherIcon name="paperclip" class="size-4" />
          <span>{{ message.attachment_type || __('Attachment') }}</span>
        </a>
        <div
          v-if="message.direction === 'Outgoing'"
          class="mt-1 text-right text-xs text-ink-gray-5"
        >
          {{ __(message.delivery_status) }}
        </div>
      </div>
    </div>
  </div>
  <Dialog
    v-model="showCodeDialog"
    :options="{ title: __('Channel link code') }"
  >
    <template #body-content>
      <div class="flex flex-col gap-4">
        <p class="text-p-base text-ink-gray-6">
          {{
            __(
              'Send this code to the client and ask them to send it as the first message in the new channel. The conversation will be linked without creating another lead.',
            )
          }}
        </p>
        <div
          class="flex items-center justify-between rounded-md bg-surface-gray-2 px-4 py-3"
        >
          <code class="text-xl font-semibold tracking-wider text-ink-gray-9">
            {{ handoff?.code }}
          </code>
          <Button :label="__('Copy')" icon-left="copy" @click="copyCode" />
        </div>
        <div class="text-sm text-ink-gray-5">
          {{ __('Valid until {0}', [formatDate(handoff?.expires_at)]) }}
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { formatDate, timeAgo } from '@/utils'
import { Button, Dialog, Tooltip, call, toast } from 'frappe-ui'
import { ref } from 'vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  referenceDoctype: { type: String, required: true },
  referenceName: { type: String, required: true },
})

const creatingCode = ref(false)
const showCodeDialog = ref(false)
const handoff = ref(null)

async function createHandoff() {
  creatingCode.value = true
  try {
    handoff.value = await call('crm.api.omnichannel.create_channel_handoff', {
      reference_doctype: props.referenceDoctype,
      reference_name: props.referenceName,
    })
    showCodeDialog.value = true
  } catch (error) {
    toast.error(error.messages?.[0] || __('Failed to create channel link code'))
  } finally {
    creatingCode.value = false
  }
}

async function copyCode() {
  if (!handoff.value?.code) return
  await navigator.clipboard.writeText(handoff.value.code)
  toast.success(__('Channel link code copied'))
}
</script>
