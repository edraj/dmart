<script lang="ts">
  import pkg from "prismjs";
  const {highlight, languages} = pkg;
  import "prismjs/components/prism-json";
  import "prismjs/components/prism-bash";

  let {language = "json", code = $bindable()} : {language?: string | null, code: object | string} = $props();

  let formatted: string = $state("{}");
  $effect(() => {
    formatted = highlight(language=="json"?JSON.stringify(code, undefined,1):code as string,languages[language],language);
  })
</script>

<pre class="language-{language}" data-output="2-17">
  <code class="language-{language}">{@html formatted}</code>
</pre>

<style global>
  @import "prismjs/themes/prism.css";
  @import "prismjs/themes/prism-coy.css";

  pre {
    display:grid;
    margin-top: 0px !important;
    font-size: 80% !important;
  }
</style>
