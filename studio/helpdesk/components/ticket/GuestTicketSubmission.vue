<template>
  <section class="mx-auto flex w-full max-w-2xl flex-col gap-5 px-4 py-8">
    <div v-if="verified" class="rounded-lg border border-outline-gray-2 p-6">
      <h1 class="text-xl font-semibold text-ink-gray-9">{{ __('Request submitted') }}</h1>
      <p class="mt-2 text-ink-gray-6">{{ __('Your email address is verified. Your request has been recorded.') }}</p>
      <p v-if="ticketName" class="mt-3 font-medium">{{ __('Ticket reference: {0}', [ticketName]) }}</p>
      <p class="mt-2 text-sm text-ink-gray-6">{{ __('Agent replies and ticket status changes will be sent to your email address.') }}</p>
    </div>

    <div v-else-if="verificationToken && !verificationError" class="rounded-lg border border-outline-gray-2 p-6">
      <h1 class="text-xl font-semibold text-ink-gray-9">{{ __('Confirm your email') }}</h1>
      <p class="mt-2 text-ink-gray-6">{{ __('Confirm that you own this email address to submit your helpdesk request.') }}</p>
      <Button class="mt-4" size="md" variant="solid" :loading="verifying" :label="__('Confirm email and submit request')" @click="verify" />
    </div>

    <div v-else-if="verificationError" role="alert" class="rounded-lg border border-outline-gray-2 p-6">
      <h1 class="text-xl font-semibold text-ink-gray-9">{{ __('Verification unavailable') }}</h1>
      <p class="mt-2 text-ink-gray-6">{{ verificationError }}</p>
    </div>

    <form v-else class="flex flex-col gap-4" @submit.prevent="submit">
      <div>
        <h1 class="text-2xl font-semibold text-ink-gray-9">{{ __('Submit a request') }}</h1>
        <p class="mt-1 text-sm text-ink-gray-6">{{ __('No account is required. We will verify your email before creating the ticket.') }}</p>
      </div>
      <FormControl v-model="form.full_name" type="text" :label="__('Name (optional)')" :placeholder="__('Your name')" />
      <FormControl v-model="form.email" type="email" required :label="__('Email address')" :placeholder="__('you@example.com')" />
      <FormControl v-model="form.office" type="select" required :label="__('Office')" :options="officeOptions" :placeholder="__('Select an office')" />
      <FormControl v-model="form.request_type" type="select" required :label="__('Type of request')" :options="requestTypeOptions" :placeholder="__('Select a request type')" />
      <FormControl v-model="form.subject" type="text" required maxlength="140" :label="__('Subject')" :placeholder="__('A short description')" />
      <div class="flex flex-col gap-1.5">
        <label for="guest-description" class="text-sm font-medium text-ink-gray-7">{{ __('Description') }}</label>
        <textarea id="guest-description" v-model="form.description" required maxlength="10000" rows="7" class="w-full rounded-md border border-outline-gray-2 bg-surface-white p-3 text-sm" :placeholder="__('Describe the issue and any relevant details…')" />
      </div>
      <p class="text-xs text-ink-gray-5">{{ __('Attachments are not available in this guest submission flow. Please do not include passwords or other sensitive information.') }}</p>
      <p v-if="error" role="alert" class="text-sm text-ink-red-6">{{ error }}</p>
      <Button type="submit" size="md" variant="solid" :loading="submitting" :disabled="!canSubmit" :label="__('Send verification email')" />
      <p v-if="sent" role="status" class="text-sm text-ink-gray-6">{{ __('If the request is valid, a verification email has been sent. Check your inbox and follow the link within 30 minutes.') }}</p>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Button, FormControl, call } from 'frappe-ui'
import { __ } from '@helpdesk/shared/translation'

const route = useRoute()
const form = reactive({ full_name: '', email: '', office: '', request_type: '', subject: '', description: '' })
const offices = ref<any[]>([])
const requestTypes = ref<any[]>([])
const submitting = ref(false)
const verifying = ref(false)
const sent = ref(false)
const verified = ref(false)
const verificationToken = ref('')
const verificationError = ref('')
const ticketName = ref('')
const error = ref('')
const officeOptions = computed(() => offices.value.map(row => ({ label: row.office_name, value: row.name })))
const requestTypeOptions = computed(() => requestTypes.value.filter(row => row.office === form.office).map(row => ({ label: row.request_type_name, value: row.name })))
const canSubmit = computed(() => Boolean(form.email.trim() && form.office && form.request_type && form.subject.trim() && form.description.trim()))

watch(() => form.office, () => { form.request_type = '' })

onMounted(async () => {
  const token = typeof route.query.verify === 'string' ? route.query.verify : ''
  if (token) {
    // Do not consume the token on page load; mail security scanners may prefetch links.
    verificationToken.value = token
    return
  }
  try {
    const result = await call('helpdesk.anonymous_tickets.get_guest_form_options')
    offices.value = result.offices || []
    requestTypes.value = result.request_types || []
    form.office = offices.value.find(row => row.is_default)?.name || offices.value[0]?.name || ''
  } catch {
    error.value = __('Could not load the request form. Please refresh the page or contact the helpdesk.')
  }
})

async function verify() {
  if (!verificationToken.value || verifying.value) return
  verifying.value = true
  verificationError.value = ''
  try {
    const result = await call('helpdesk.anonymous_tickets.verify_guest_submission', { token: verificationToken.value })
    ticketName.value = result.ticket
    verified.value = Boolean(result.success)
    verificationToken.value = ''
  } catch {
    verificationError.value = __('This verification link is invalid, expired, or could not be processed. Please submit a new request.')
  } finally {
    verifying.value = false
  }
}

async function submit() {
  if (!canSubmit.value || submitting.value) return
  submitting.value = true
  error.value = ''
  sent.value = false
  try {
    await call('helpdesk.anonymous_tickets.start_guest_submission', { ...form })
    sent.value = true
  } catch (e: any) {
    error.value = e?.messages?.[0] || e?.message || __('Could not send the verification email. Please try again later.')
  } finally {
    submitting.value = false
  }
}
</script>
