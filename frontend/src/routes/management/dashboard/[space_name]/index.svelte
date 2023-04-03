<script>
  import { params } from "@roxi/routify";
  $: {
    console.log({ s: $params });
  }
</script>
