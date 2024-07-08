<script lang="ts">
  import { _, switchLocale, locale, available_locales } from "@/i18n";
  import { website } from "@/config";
  import { ButtonGroup, Button } from "sveltestrap";
  // import { formToJSON } from "axios";
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
      active={key === $locale}
      size="sm"
      on:click={
        function(event) {

          let path = document.URL  
          if (path.charAt(path.length-3) === ".") {
            path = path.substring(0, path.length-3) 
          }
          if (key !== "en") {
              path += "." + key
          }
          selectLocale(event, key)
          window.location.replace(path);
        }
      }>{key}</Button
    >
  {/each}
</ButtonGroup>
