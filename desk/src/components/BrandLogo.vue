<template>
  <img
    :src="config.brandLogo"
    :alt="config.brandName"
    class="h-8 w-8 shrink-0 object-contain"
  />
</template>

<script setup lang="ts">
import { useConfigStore } from "@/stores/config";

const config = useConfigStore();
</script>
