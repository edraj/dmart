<script>
    import {Button, Input, Table,} from 'flowbite-svelte';
    import {TrashBinSolid} from 'flowbite-svelte-icons';

    export let entries = [];

    let tempNew = {}
    function appendEntry(){
        entries = [...entries, tempNew];
        tempNew = {};
    }

    function removeEntry(index) {
        entries.splice(index, 1);
        entries = [...entries];
    }
</script>

<Table>
  <thead>
  <tr>
    <th>Key</th>
    <th>Value</th>
    <th>Action</th>
  </tr>
  </thead>
  <tbody>
    {#each entries as entry, index}
      <tr>
        <td><Input bind:value={entry["key"]} /></td>
        <td><Input bind:value={entry["value"]} /></td>
        <td><Button class="cursor-pointer bg-red-600" onclick={() => removeEntry(index)}><TrashBinSolid size="sm" /></Button></td>
      </tr>
    {/each}
    <tr>
      <td><Input bind:value={tempNew["key"]} placeholder={"New key"} /></td>
      <td><Input bind:value={tempNew["value"]} placeholder={"New value"} /></td>
      <td><Button class="cursor-pointer bg-primary" onclick={appendEntry}>Add</Button></td>
    </tr>
  </tbody>
</Table>
