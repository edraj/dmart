<script>
  import { Container, Col, Label, Input, Button } from "sveltestrap";
  import spaces from "../_stores/spaces";
  import { triggerSidebarSelection } from "../_stores/triggers";

  const form = {
    type: "",
    space_name: "",
    subpath: "",
    shortname: "",
    search: "*",
    offset: 0,
    limit: 50,
  };

  function onchange(e) {
    const { name, value } = e.target;
    form[name] = value;
  }

  async function handleSubmit() {
    triggerSidebarSelection.set(form);
  }
</script>

<Container class="mt-5">
  <Col>
    <Label class="mt-2 mx-2">Query type</Label>
    <Input name="type" type="select" on:change={onchange}>
      <option value="subpath">Subpath</option>
      <option value="search">Search</option>
    </Input>
    <Label class="mt-2 mx-2">Space</Label>
    <Input name="space_name" type="select" on:change={onchange}>
      {#each $spaces.children as space}
        <option value={space.shortname}>
          {space.shortname}
        </option>
      {/each}</Input
    >
    <Label class="mt-2 mx-2">Subpath</Label>
    <Input name="subpath" on:keyup={onchange} />
    <Label class="mt-2 mx-2">Shortnames</Label>
    <Input name="shortname" on:keyup={onchange} />
    <Label class="mt-2 mx-2">Search</Label>
    <Input name="search" value={form.search} on:keyup={onchange} />
    <Label class="mt-2 mx-2">Limit</Label>
    <Input name="limit" type="number" value={form.limit} on:keyup={onchange} />
    <Label class="mt-2 mx-2">Offset</Label>
    <Input
      name="offset"
      type="number"
      value={form.offset}
      on:keyup={onchange}
    />
    <Button class="w-100 mt-5" color={"primary"} on:click={handleSubmit}
      >Execute</Button
    >
  </Col>
</Container>
