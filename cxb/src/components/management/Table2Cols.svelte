<script lang="ts">
    import {Table, TableBody, TableBodyCell, TableBodyRow, TableHead, TableHeadCell} from "flowbite-svelte";

    export let entry = {};

  function renderNestedObject(obj: any) {
      let str = "<ul class='mx-5'>";
      Object.entries(obj).map(([key, value]) => {
          str += "<li>";
          str += `<b>${key}: </b>`;
          str += renderValue(value);
          str += "</li>";
      });
      return str += "</ul>";
  }

  function renderValue(data: any) {
   if (data === null){
       return "N/A";
   }
   if (typeof(data) === "object"){
       return renderNestedObject(data);
   }

   return data;
  }
</script>

<div class="h-full" style="overflow-y: auto;">
  <Table class="h-full" striped>
    <TableHead>
        <TableHeadCell>Key</TableHeadCell>
        <TableHeadCell>Value</TableHeadCell>
    </TableHead>
    <TableBody>
        {#each Object.keys(entry) as key}
          <TableBodyRow>
            <TableBodyCell>{key}</TableBodyCell>
            <TableBodyCell>{@html renderValue(entry[key])}</TableBodyCell>
          </TableBodyRow>
        {/each}
    </TableBody>
  </Table>
</div>
