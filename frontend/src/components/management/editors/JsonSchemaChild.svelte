<script>
  import { generateUUID } from "@/utils/uuid";
  import { Col, Row, Input, Icon } from "sveltestrap";

  export let parent;
  export let item;
  export let refresh;
  export let parentRefresh;
  export let root = false;

  const types = ["string", "number", "array", "object", "boolean", "integer"];

  function handleAddChildren() {
    item.properties = [
      ...(item?.properties ?? []),
      {
        id: generateUUID(),
        name: "",
        type: "string",
        title: "",
        description: "",
      },
    ];

    refresh();
  }
  function handleDeleteParent() {
    if (root){
      return;
    }
    parent = parent.filter((e) => e.id !== item.id);
    parentRefresh(parent);
  }

  function handleParentRefresh(newParent) {
    item.properties = newParent;
  }

  $: parent && refresh();
  $: item && refresh();
</script>

<Row class="my-3">
  <Col sm={4}
    ><Input type="text" placeholder="title...." bind:value={item.title} /></Col
  >
  <Col sm={3}
    ><Input
      type="text"
      placeholder="description...."
      bind:value={item.description}
    /></Col
  >
  <Col sm={3}
    ><Input type="select" bind:value={item.type}>
      {#each types as type}
        <option value={type}>{type}</option>
      {/each}
    </Input></Col
  >
  {#if ["array", "object"].includes(item.type)}
    <Col class="align-self-center" sm={1}
      ><Icon name="plus-square-fill" onclick={() => handleAddChildren()} /></Col
    >
  {/if}
  {#if !root}
    <Col class="align-self-center" sm={1}
      ><Icon name="trash-fill" onclick={() => handleDeleteParent()} /></Col
    >
  {/if}
</Row>
<div style="padding-left: 8px">
  {#if item.properties}
    {#key item.properties}
      {#each item.properties as prop}
        <svelte:self
          parent={item.properties}
          item={prop}
          {refresh}
          parentRefresh={handleParentRefresh}
        />
      {/each}
    {/key}
  {/if}
</div>
