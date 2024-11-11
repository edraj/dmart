<script lang="ts">
  import { locale } from "@/i18n";

  let { field } = $props();

  let value: string = $state("");

  $effect(() => {
    if (typeof field === "object") {
      if (field[$locale]) {
        value = field[$locale];
      } else {
        value = Object.values(field)[0];
      }
    } else if (typeof field === "string") {
      value = field;
    }
  });
</script>

{@html value}
