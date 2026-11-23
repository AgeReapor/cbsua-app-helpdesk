<template>
  <section class="mx-auto flex w-full max-w-xl flex-col gap-5 px-4 py-8">
    <div v-if="verified" class="rounded-lg border border-outline-gray-2 p-6">
      <h1 class="text-xl font-semibold text-ink-gray-9">
        {{ __('Request submitted') }}
      </h1>
      <p class="mt-2 text-ink-gray-6">
        {{ __('Your email address is verified. Your request has been recorded.') }}
      </p>
      <p v-if="ticketName" class="mt-3 font-medium">
        {{ __('Ticket reference: {0}', [ticketName]) }}
      </p>
      <p class="mt-2 text-sm text-ink-gray-6">
        {{ __('Agent replies and ticket status changes can be sent to your email address when Helpdesk email delivery is enabled.') }}
      </p>
    </div>

    <div v-else-if="challengeId && !verified" class="rounded-lg border border-outline-gray-2 p-6">
      <h1 class="text-xl font-semibold text-ink-gray-9">{{ __('Check your email') }}</h1>
      <p class="mt-2 text-ink-gray-6">
        {{ __('Enter the six-digit code sent to {0}. The code expires in 10 minutes.', [maskedEmail]) }}
      </p>
      <form class="mt-4 flex flex-col gap-3" @submit.prevent="verify">
        <FormControl
          v-model="otp"
          type="text"
          inputmode="numeric"
          autocomplete="one-time-code"
          maxlength="6"
          :label="__('Email verification code')"
          :placeholder="__('000000')"
        />
        <p v-if="verificationError" role="alert" class="text-sm text-ink-red-6">{{ verificationError }}</p>
        <Button type="submit" size="md" variant="solid" :loading="verifying"
          :disabled="otp.length !== 6" :label="__('Verify and submit request')" />
      </form>
      <div class="mt-4 flex items-center justify-between gap-3">
        <span class="text-sm text-ink-gray-6">{{ __('Did not receive the code?') }}</span>
        <Button size="sm" variant="outline" :loading="resending" :disabled="resendWait > 0 || resends >= 3"
          :label="resendWait > 0 ? __('Resend in {0}s', [resendWait]) : __('Resend code')"
          @click="resendOtp" />
      </div>
    </div>

    <form v-else class="flex flex-col gap-4" @submit.prevent="submit">
      <div>
        <h1 class="text-2xl font-semibold text-ink-gray-9">
          {{ __('Submit a request') }}
        </h1>
        <p class="mt-1 text-sm text-ink-gray-6">
          {{ __('No account is required. We will email you a one-time code before creating the ticket.') }}
        </p>
      </div>

      <FormControl
        v-model="form.full_name"
        type="text"
        maxlength="140"
        :label="__('Name (optional)')"
        :placeholder="__('Your name')"
      />
      <FormControl
        v-model="form.email"
        type="email"
        required
        :label="__('Email address')"
        :placeholder="__('you@example.com')"
      />

      <div class="grid w-full grid-cols-1 gap-3 sm:grid-cols-2">
        <div class="flex flex-col gap-1.5">
          <label
            for="guest-office"
            class="text-sm font-medium text-ink-gray-7"
          >
            {{ __('Office') }}
          </label>
          <Combobox
            id="guest-office"
            v-model="form.office"
            trigger="button"
            size="sm"
            :options="officeOptions"
            :placeholder="__('Select an office')"
            :required="true"
            :disabled="loadingOptions || !officeOptions.length"
            :loading="loadingOptions"
          />
        </div>
        <div class="flex flex-col gap-1.5">
          <label
            for="guest-request-type"
            class="text-sm font-medium text-ink-gray-7"
          >
            {{ __('Type of request') }}
          </label>
          <Combobox
            id="guest-request-type"
            v-model="form.request_type"
            trigger="button"
            size="sm"
            :options="requestTypeOptions"
            :placeholder="__('Select a request type')"
            :required="true"
            :disabled="!form.office || loadingOptions || !requestTypeOptions.length"
          />
        </div>
      </div>
      <p v-if="optionsError" role="alert" class="text-sm text-ink-red-6">
        {{ optionsError }}
      </p>
      <p
        v-else-if="form.office && !loadingOptions && !requestTypeOptions.length"
        role="alert"
        class="text-sm text-ink-gray-6"
      >
        {{ __('No request types are available for this office.') }}
      </p>

      <FormControl
        v-model="form.subject"
        type="text"
        required
        maxlength="140"
        :label="__('Subject')"
        :placeholder="__('A short description')"
      />
      <div class="flex flex-col gap-1.5">
        <label
          for="guest-description"
          class="text-sm font-medium text-ink-gray-7"
        >
          {{ __('Description') }}
        </label>
        <textarea
          id="guest-description"
          v-model="form.description"
          required
          maxlength="10000"
          rows="7"
          class="w-full rounded-md border border-outline-gray-2 bg-surface-white p-3 text-sm"
          :placeholder="__('Describe the issue and any relevant details…')"
        />
      </div>

      <p class="text-xs text-ink-gray-5">
        {{ __('Attachments are not available in this guest submission flow. Please do not include passwords or other sensitive information.') }}
      </p>
      <p v-if="error" role="alert" class="text-sm text-ink-red-6">
        {{ error }}
      </p>
      <Button
        type="submit"
        size="md"
        variant="solid"
        :loading="submitting"
        :disabled="!canSubmit || sent"
        :label="__('Email me a verification code')"
      />
      <p v-if="sent" role="status" class="text-sm text-ink-gray-6">
        {{ __('If the request is valid, a verification email has been sent. Check your inbox and follow the link within 30 minutes.') }}
      </p>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { Button, Combobox, FormControl, call } from 'frappe-ui'
import { __ } from '@helpdesk/shared/translation'


const form = reactive({
  full_name: '',
  email: '',
  office: '',
  request_type: '',
  subject: '',
  description: '',
})

const offices = ref<any[]>([])
const requestTypes = ref<any[]>([])
const loadingOptions = ref(true)
const optionsError = ref('')
const submitting = ref(false)
const verifying = ref(false)
const sent = ref(false)
const challengeId = ref('')
const otp = ref('')
const maskedEmail = ref('')
const resending = ref(false)
const resends = ref(0)
const resendWait = ref(0)
const verified = ref(false)
const verificationError = ref('')
const verificationErrorCode = ref('')
const ticketName = ref('')
const error = ref('')

const officeOptions = computed(() =>
  offices.value.map((row) => ({
    label: row.office_name,
    value: row.name,
  }))
)

const requestTypeOptions = computed(() =>
  requestTypes.value
    .filter((row) => row.office === form.office)
    .map((row) => ({
      label: row.request_type_name,
      value: row.name,
    }))
)

const canSubmit = computed(() =>
  Boolean(
    form.email.trim() &&
      form.office &&
      form.request_type &&
      form.subject.trim() &&
      form.description.trim()
  )
)

watch(
  () => form.office,
  () => {
    form.request_type = ''
  }
)

watch(
  form,
  () => {
    sent.value = false
  },
  { deep: true }
)

onMounted(async () => {
  try {
    const result = await call('helpdesk.anonymous_tickets.get_guest_form_options')
    offices.value = result.offices || []
    requestTypes.value = result.request_types || []
    if (!offices.value.length) {
      optionsError.value = __('No offices are currently available. Please contact the helpdesk.')
    }
    form.office =
      offices.value.find((row) => row.is_default)?.name ||
      offices.value[0]?.name ||
      ''
  } catch {
    optionsError.value = __(
      'Could not load office options. Please refresh the page or contact the helpdesk.'
    )
  } finally {
    loadingOptions.value = false
  }
})

async function verify() {
  if (!challengeId.value || otp.value.length !== 6 || verifying.value) return
  verifying.value = true
  verificationError.value = ''
  try {
    const result = await call('helpdesk.anonymous_tickets.verify_guest_submission', {
      challenge_id: challengeId.value,
      otp: otp.value,
    })
    if (!result?.success) {
      const code = result?.code
      verificationError.value =
        code === 'invalid_code'
          ? __('That code is incorrect. {0} attempts remaining.', [result.attempts_remaining])
          : code === 'too_many_attempts'
            ? __('Too many incorrect attempts. Request a new code if this challenge is still available.')
            : code === 'cooldown'
              ? __('Please wait before requesting another code.')
              : code === 'processing'
                ? __('Your request is being processed. Please try again shortly.')
                : __('The code has expired or is no longer valid. Please start a new request.')
      if (code === 'too_many_attempts' || code === 'invalid_or_expired') {
        challengeId.value = ''
      }
      return
    }
    ticketName.value = result.ticket
    verified.value = true
    challengeId.value = ''
    otp.value = ''
  } catch {
    verificationError.value = __('Verification is temporarily unavailable. Try again shortly. Do not submit a duplicate request.')
  } finally {
    verifying.value = false
  }
}

async function resendOtp() {
  if (!challengeId.value || resending.value || resendWait.value > 0) return
  resending.value = true
  verificationError.value = ''
  try {
    const result = await call('helpdesk.anonymous_tickets.resend_guest_submission_otp', {
      challenge_id: challengeId.value,
    })
    if (!result?.success) {
      verificationError.value =
        result?.code === 'cooldown'
          ? __('Please wait before requesting another code.')
          : result?.code === 'resend_limit'
            ? __('You have reached the resend limit. Start a new request.')
            : __('Could not resend the code. Please try again.')
      if (result?.code === 'invalid_or_expired' || result?.code === 'resend_limit') challengeId.value = ''
      return
    }
    otp.value = ''
    resends.value += 1
    resendWait.value = 60
    const timer = window.setInterval(() => {
      resendWait.value = Math.max(0, resendWait.value - 1)
      if (!resendWait.value) window.clearInterval(timer)
    }, 1000)
  } catch {
    verificationError.value = __('Could not resend the code. Please try again later.')
  } finally {
    resending.value = false
  }
}

async function submit() {
  if (!canSubmit.value || submitting.value || sent.value) return

  submitting.value = true
  error.value = ''
  sent.value = false
  try {
    const result = await call('helpdesk.anonymous_tickets.start_guest_submission', { ...form })
    challengeId.value = result.challenge_id
    maskedEmail.value = form.email.replace(/^(.).+(@.+)$/, '$1•••$2')
    sent.value = true
  } catch (e: any) {
    error.value =
      e?.messages?.[0] ||
      e?.message ||
      __('Could not send the verification email. Please try again later.')
  } finally {
    submitting.value = false
  }
}
</script>
