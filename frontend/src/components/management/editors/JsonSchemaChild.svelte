<script lang="ts">
  import { generateUUID } from "@/utils/uuid";
  import {Col, Row, Input, Icon, Card, Label} from "sveltestrap";

  export let parent;
  export let item;
  export let refresh;
  export let parentRefresh;
  export let root = false;

  $: isRequired = !!parent?.required?.includes(item.name);

  const types = ["string", "number", "array", "object", "boolean", "integer"];

  function handleAddChildren() {
    if (item.type==="array"){
        if (item?.items === undefined){
            item.items = {}
        }
        item.items.properties = [
            ...(item?.items?.properties ?? []),
            {
                id: generateUUID(),
                name: "",
                type: "string",
                title: "",
                description: "",
            },
        ];
    } else {
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
    }

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
    if (newParent.required){
        item.required = newParent.required;
    }
    item.properties = newParent;
  }

  $: parent && refresh();
  $: item && refresh();

  let oldType = item.type.toString();
  $: {
    if (item.type !== oldType) {
      if (oldType==="number" || oldType==="integer"){
          delete item.minimum;
          delete item.maximum;
      } else if (oldType==="string") {
          delete item.minLength;
          delete item.maxLength;
          delete item.enum;
          delete item.pattern;
      } else if (oldType==="array") {
          delete item.minItems;
          delete item.maxItems;
          delete item.uniqueItems;
      }
      oldType = item.type.toString();
      refresh();
    }
  }

  function handleRequired(e: any){
      e.preventDefault();
      e.stopPropagation();

      if (e.target.checked){
        if (parent.required){
            parent.required = [...parent.required, item.name];
        } else {
            parent.required = [item.name];
        }
      } else {
          if (parent.required){
              parent.required = parent.required.filter(prop => prop !== item.name);
          }
      }
      parentRefresh(parent);
  }

  let isDisplayFilter = false;
</script>

<Card>
  <Row class="my-3 mx-1">
    <Col sm={2}>
      <Input type="text" placeholder="title...." bind:value={item.name} />
    </Col>
    <Col sm={2}>
      <Input type="text" placeholder="title...." bind:value={item.title} />
    </Col>
    <Col sm={3}>
      <Input  type="text"  placeholder="description...."  bind:value={item.description} />
    </Col>
    <Col sm={2}>
      <Input type="select" bind:value={item.type}>
        {#each types as type}
          <option value={type}>{type}</option>
        {/each}
      </Input>
    </Col>
    {#if ["array", "object"].includes(item.type)}
      <Col class="align-self-center" sm={1}>
        <Icon name="plus-square-fill" onclick={handleAddChildren} />
      </Col>
    {/if}
    {#if !root}
      <Col class="align-self-center" sm={1}>
        <Icon name="trash-fill" onclick={handleDeleteParent} />
      </Col>
      <Col class="align-self-center" sm={1}>
        <Icon name={isDisplayFilter ? "filter-circle-fill" : "filter-circle"}
          onclick={() => (isDisplayFilter = !isDisplayFilter)}/>
      </Col>
    {/if}
    {#if isDisplayFilter}
      <Row class="my-3 mx-1">
        {#if item.type === "number" || item.type === "integer"}
          <Col sm="6">
            <Label>Minimum</Label>
            <Input type="number" label="Minimum" bind:value={item.minimum} />
          </Col>
          <Col class="mt-2" sm="6">
            <Label>Maximum</Label>
            <Input type="number" label="Maximum" bind:value={item.maximum} />
          </Col>
        {:else if item.type === "string"}
          <Col sm="6">
            <Label>Minimum Length</Label>
            <Input type="number" label="Minimum" bind:value={item.minLength} />
          </Col>
          <Col class="mt-2" sm="6">
            <Label>Maximum Length</Label>
            <Input type="number" label="Maximum" bind:value={item.maxLength} />
          </Col>
          <Col class="mt-2" sm="12">
            <Label>Enum (male,female)</Label>
            <Input type="text"
                 on:change={(e)=>{item.enum=e.target.value.split(",")}} />
          </Col>
          <Col class="mt-2" sm="12">
            <Label>Pattern</Label>
            <Input type="text" bind:value={item.pattern} />
          </Col>
        {:else if item.type === "array"}
          <Col sm="6">
            <Label>Minimum Items</Label>
            <Input type="number" bind:value={item.minItems} />
          </Col>
          <Col class="mt-2" sm="6">
            <Label>Maximum Items</Label>
            <Input type="number" bind:value={item.maxItems} />
          </Col>
          <Col class="mt-2" sm="6">
            <Input type="checkbox" label="Unique Items?" bind:checked={item.uniqueItems} />
          </Col>
        {/if}
      </Row>
      <Row class="my-1 mx-1">
        <Input type="checkbox" label="Is required?"
           on:change={handleRequired}
           checked={isRequired} />
      </Row>
    {/if}
  </Row>
  <div class="px-2 py-1">
    {#if item.properties}
      {#key item.properties}
        {#each (item?.properties ?? []) as prop}
          <svelte:self
            parent={item.properties}
            item={prop}
            {refresh}
            parentRefresh={handleParentRefresh}
          />
        {/each}
      {/key}
    {:else if item.items}
      {#key item.items.properties}
        {#each (item?.items?.properties ?? []) as prop}
          <svelte:self
            parent={item.items.properties}
            item={prop}
            {refresh}
            parentRefresh={handleParentRefresh}
          />
        {/each}
      {/key}
    {/if}
  </div>
</Card>
