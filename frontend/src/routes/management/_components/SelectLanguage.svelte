<script>
  import { _, switchLocale, locale, available_locales } from "../../../i18n/index.js";
  import { website } from "../../../config.js";
  import { ButtonGroup, Button } from "sveltestrap";
  let locales = available_locales.filter((x) => x in website.languages);

  function selectLocale(_locale) {
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
      on:click={() => selectLocale(key)}>{key}</Button
    >
  {/each}
</ButtonGroup>
