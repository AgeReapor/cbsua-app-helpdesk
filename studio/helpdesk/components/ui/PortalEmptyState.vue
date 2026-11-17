<template>
  <div
    class="flex flex-col items-center justify-center gap-4 py-16 text-center"
  >
    <div
      class="flex size-16 items-center justify-center rounded-full bg-surface-gray-1"
    >
      <component :is="glyph" class="size-6 text-ink-gray-7" />
    </div>
    <div class="flex flex-col items-center gap-1">
      <!-- A clear title/description contrast makes empty states scannable. -->
      <div class="text-base font-semibold text-ink-gray-9">{{ title }}</div>
      <div v-if="description" class="max-w-72 text-p-sm text-ink-gray-6">
        {{ description }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import LucideBuilding2 from "~icons/lucide/building-2";
import LucideInbox from "~icons/lucide/inbox";
import PortalArticleIcon from "@helpdesk/shared/ArticleIcon.vue";

const GLYPHS = {
  organization: LucideBuilding2,
  article: PortalArticleIcon,
  ticket: LucideInbox,
};

const props = withDefaults(
  defineProps<{
    title: string;
    description?: string;
    icon?: keyof typeof GLYPHS;
  }>(),
  { icon: "article" }
);

const glyph = computed(() => GLYPHS[props.icon] || GLYPHS.article);
</script>
