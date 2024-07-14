<script lang="ts">
  import { locale } from "@/i18n";

  export let field : string | object;
  let value: string;

  $: {
    if (typeof field === "object") {
      if (field[$locale]) {
        value = field[$locale];
      } else {
        value = Object.values(field)[0];
      }
    } else if (typeof field === "string") {
      value = field;
    }

    let language = localStorage.getItem("preferred_locale").substring(1,3)

    if ( language === "ar") {
      const elements = document.querySelectorAll(".language-json");
      elements.forEach(element => {
        element.setAttribute("dir", "ltr");
      }); 
    } 
  }
</script>

{@html value}
