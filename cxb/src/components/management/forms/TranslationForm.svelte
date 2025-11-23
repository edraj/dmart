<script lang="ts">
    import {Button, Card, Input, Table,} from 'flowbite-svelte';
    import {PlusOutline, TrashBinSolid} from 'flowbite-svelte-icons';

    let {
      entries = $bindable(),
      columns
    } = $props();

    entries = {
      items: entries.items || []
    }

    let tempNew = $state({});
    function appendEntry(){
        entries.items = [...entries.items, tempNew];
        tempNew = {};
    }

    function removeEntry(index) {
        entries.items.splice(index, 1);
        entries.items = [...entries.items];
    }
</script>
<Card class="p-4 max-w-4xl mx-auto my-2">
  <h1 class="text-2xl font-bold mb-4">Translation Form</h1>
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

    {#each entries.items as entry, index}
      <tr class="mt-2">
        {#each columns as key}
          <td><Input bind:value={entry[key]} /></td>
        {/each}
        <td><Button class="cursor-pointer bg-red-600" onclick={() => removeEntry(index)}><TrashBinSolid size="sm" /></Button></td>
      </tr>
    {/each}
    <tr class="mt-2">
      {#each columns as key}
        <td><Input bind:value={tempNew[key]} placeholder={`New ${key}`} /></td>
      {/each}
      <td><Button class="cursor-pointer bg-primary" onclick={appendEntry}><PlusOutline size="sm" /></Button></td>
    </tr>
  </tbody>
</Table>
</Card>

