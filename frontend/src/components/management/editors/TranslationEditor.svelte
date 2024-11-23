<script>
    import {
        Table,
        Button,
        Input,
    } from 'sveltestrap';
    import Icon from "@/components/Icon.svelte";

    export let entries = [];
    export let columns = [];

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
    {#each columns as key}
      <th>{key[0].toUpperCase() + key.slice(1)}</th>
    {/each}
      <th>Action</th>
  </tr>
  </thead>
  <tbody>
    {#each entries as entry, index}
      <tr>
        {#each columns as key}
          <td><Input bind:value={entry[key]} /></td>
        {/each}
        <td><Button onclick={() => removeEntry(index)}><Icon name="trash" /></Button></td>
      </tr>
    {/each}
    <tr>
      {#each columns as key}
        <td><Input bind:value={tempNew[key]} placeholder={`New ${key}`} /></td>
      {/each}
      <td><Button onclick={appendEntry}>Add</Button></td>
    </tr>
    </tbody>
</Table>

