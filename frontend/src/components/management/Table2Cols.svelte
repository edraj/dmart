<script lang="ts">
  import { Table } from "sveltestrap";
  import { _, number } from "@/i18n";

  export let entry = {};

  function renderNestedObject(obj: any) {
      let str = "<ul>";
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

<div class="h-100" style="overflow-y: auto;">
  <Table class="h-100 " hover responsive striped>
    <thead>
      <tr>
        <th>Key</th>
        <th>Value</th>
      </tr>
    </thead>
    <tbody>
        {#each Object.keys(entry) as key}
          <tr>
            <td>{key}</td>
            <td>{@html renderValue(entry[key])}</td>
          </tr>
        {/each}
    </tbody>
  </Table>
</div>
