<template>
  <!-- Keep the complete institutional mark visible; don't crop it into an avatar. -->
  <img
    :src="config.brandLogo"
    :alt="config.brandName"
    class="h-8 w-8 shrink-0 rounded-4 bg-surface-gray-1 p-1 object-contain ring-1 ring-outline-gray-2"
  />
</template>

<script setup lang="ts">
import { useConfigStore } from "@/stores/config";

const config = useConfigStore();
</script>
