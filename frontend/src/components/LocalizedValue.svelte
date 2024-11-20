<script lang="ts">
  import { locale } from "@/i18n";

  let { field } = $props();

  let value: string = $state("");

  $effect(() => {
    if (typeof field === "object") {
      if (field[$locale]) {
        value = field[$locale];
      } else {
        const _values = Object.values(field);
        if (_values.length > 0) {
          value = _values[0];
        }
      }
    } else if (typeof field === "string") {
      value = field;
    }
  });
</script>

{@html value}
