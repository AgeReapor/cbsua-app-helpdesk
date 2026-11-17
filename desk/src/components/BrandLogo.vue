<template>
  <img
    :src="config.brandLogo"
    :alt="config.brandName"
    class="h-8 w-8 shrink-0 rounded-full bg-surface-green-1 p-1 object-contain ring-1 ring-outline-green-2"
  />
</template>

<script setup lang="ts">
import { useConfigStore } from "@/stores/config";

const config = useConfigStore();
</script>
