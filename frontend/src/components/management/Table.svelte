<script lang="ts">
  import { Table } from "sveltestrap";
  import { _, number } from "@/i18n";

  export let cols = {};
  export let rows = [];

  function value(path: string, data : [], type : string) {
    if (path.length == 1 && path[0].length > 0 && path[0] in data) {
      if (type == "number") return $number(data[path[0]]);
      else if (type == "json")
        return JSON.stringify(data[path[0]], undefined, 1);
      else return data[path[0]];
    }

    if (path.length > 1 && path[0].length > 0 && path[0] in data) {
      return value(path.slice(1), data[path[0]], type);
    }

    return $_("not_applicable");
  }
</script>

<div class="h-100" style="overflow-y: auto;">
  <Table class="h-100 " hover responsive striped>
    <thead>
      <tr>
        <th> # </th>
        {#each Object.keys(cols) as col}
          <th>{cols[col].title}</th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#if rows}
        {#each rows as row, i}
          <tr>
            <th scope="row">{$number(i)}</th>
            {#each Object.keys(cols) as col}
              <td>{value(cols[col].path.split("."), row, cols[col].type)}</td>
            {/each}
          </tr>
        {/each}
      {/if}
    </tbody>
  </Table>
</div>
