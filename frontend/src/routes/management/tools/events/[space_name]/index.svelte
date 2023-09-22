<script lang="ts">
  import { QueryType } from "@/dmart";
  import ListView from "@/components/management/ListView.svelte";
  import { params } from "@roxi/routify";
  import cols_events from "@/stores/management/list_cols_events.json";
</script>

{#key $params.space_name}
  {#if $params.space_name}
    <ListView
      type={QueryType.events}
      space_name={$params.space_name}
      subpath={"/"}
      columns={cols_events}
    />
  {/if}
{/key}
