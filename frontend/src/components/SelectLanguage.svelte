<script lang="ts">
  import { _, switchLocale, locale, available_locales } from "@/i18n";
  import { website } from "@/config";
  import { ButtonGroup, Button } from "sveltestrap";
  let locales = available_locales.filter((x) => x in website.languages);

  function selectLocale(event : Event, _locale : string) {
    event.preventDefault();
    switchLocale(_locale);
  }
</script>

<ButtonGroup class="py-0">
  {#each locales as key}
    <Button
      outline
      color="primary"
      active={key == $locale}
      size="sm"
      on:click={(event) => selectLocale(event, key)}>{key}</Button
    >
  {/each}
</ButtonGroup>
