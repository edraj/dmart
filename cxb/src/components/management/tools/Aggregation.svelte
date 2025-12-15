<script lang="ts">
    import {Button, Input, Label, Select} from 'flowbite-svelte';
    import {MinusOutline, PlusOutline} from 'flowbite-svelte-icons';

    let { aggregation_data = $bindable({}) } : {aggregation_data: object} = $props();

  let currentSection = $state("load"); // Default to "load" section

  function addInput(event : any ) {
    event.preventDefault();

    aggregation_data[currentSection].push(
      currentSection === "reducers"
        ? {
            name: "",
            alias: "",
            args: "",
          }
        : ""
    );
    aggregation_data = { ...aggregation_data };
  }

  function deleteInput(event : any, index : number) {
    event.preventDefault();

    aggregation_data[currentSection].splice(index, 1);
    aggregation_data = { ...aggregation_data };
  }
</script>

<div class="space-y-4">
  <div class="flex items-center gap-2 mb-4">
    <div class="flex-grow">
      <Select bind:value={currentSection} class="w-full">
        <option value="load">Load</option>
        <option value="group_by">Group By</option>
        <option value="reducers">Reducers</option>
      </Select>
    </div>
    <Button color="blue" onclick={(e) => addInput(e)} class="flex-shrink-0">
      <PlusOutline class="mr-1" />
      Add
    </Button>
  </div>

  {#if currentSection === "reducers"}
    <div class="grid grid-cols-3 gap-4 mb-2">
      <div>
        <Label for="name" class="mb-2">Name</Label>
      </div>
      <div>
        <Label for="alias" class="mb-2">Alias</Label>
      </div>
      <div>
        <Label for="args" class="mb-2">Args</Label>
      </div>
    </div>
  {/if}

  <div class="space-y-4">
    {#each aggregation_data[currentSection] as input, index}
      {#if currentSection === "reducers"}
        <div class="grid grid-cols-3 gap-4">
          <div>
            <Input type="text" bind:value={input.name} />
          </div>
          <div>
            <Input type="text" bind:value={input.alias} />
          </div>
          <div class="flex items-center gap-2">
            <div class="flex-grow">
              <Input type="text" bind:value={input.args} />
            </div>
            <Button color="red" size="sm" onclick={(e) => deleteInput(e, index)} class="flex-shrink-0">
              <MinusOutline />
            </Button>
          </div>
        </div>
      {:else}
        <div class="flex items-center gap-2">
          <div class="flex-grow">
            <Input type="text" bind:value={aggregation_data[currentSection][index]} />
          </div>
          <Button color="red" size="sm" onclick={(e) => deleteInput(e, index)} class="flex-shrink-0">
            <MinusOutline />
          </Button>
        </div>
      {/if}
    {/each}
  </div>
</div>
