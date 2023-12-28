<script>
    import {
        Table,
        Button,
        Input,
    } from 'sveltestrap';
    import Icon from "@/components/Icon.svelte";

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
        <td><Button on:click={() => removeEntry(index)}><Icon name="trash" /></Button></td>
      </tr>
    {/each}
    <tr>
      <td><Input bind:value={tempNew["key"]} placeholder={"New key"} /></td>
      <td><Input bind:value={tempNew["value"]} placeholder={"New value"} /></td>
      <td><Button on:click={appendEntry}>Add</Button></td>
    </tr>
  </tbody>
</Table>
