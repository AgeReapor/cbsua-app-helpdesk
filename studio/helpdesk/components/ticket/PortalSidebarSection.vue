<template>
  <div>
    <button
      type="button"
      class="flex w-full items-center gap-1 rounded-5 px-4 py-3.5 text-left transition-colors hover:bg-surface-gray-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
      :aria-expanded="opened"
      @click="opened = !opened"
    >
      <span class="text-base font-semibold text-ink-gray-9">{{ label }}</span>
      <span
        class="lucide-chevron-right size-3.5 shrink-0 text-ink-gray-5 transition-transform"
        :class="{ 'rotate-90': opened }"
      />
    </button>
    <PortalCollapse :open="opened">
      <div class="px-4">
        <slot />
      </div>
    </PortalCollapse>
  </div>
</template>

<script setup lang="ts">
import { provide, ref } from "vue";
import PortalCollapse from "@app/components/ui/PortalCollapse.vue";

defineProps<{ label: string }>();

const opened = ref(true);
// Stays mounted when folded; animated children watch this to replay. The
// trigger keeps a visible keyboard focus ring as well as its pointer hover.
provide("portalSectionOpen", opened);
</script>
