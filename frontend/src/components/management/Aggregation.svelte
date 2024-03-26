<script lang="ts">
  import { Button, Col, Input, Row } from "sveltestrap";
  import Icon from "../Icon.svelte";

  export let aggregation_data;

  let currentSection = "load"; // Default to "load" section

  function addInput(event) {
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

  function deleteInput(event, index) {
    event.preventDefault();

    aggregation_data[currentSection].splice(index, 1);
    aggregation_data = { ...aggregation_data };
  }
</script>

<main>
  <Row class="justify-content-between">
    <div class="input-group mb-2">
      <Input type="select" bind:value={currentSection}>
        <option value="load">Load</option>
        <option value="group_by">Group By</option>
        <option value="reducers">Reducers</option>
      </Input>
      <div class="input-group-append">
        <Button on:click={(e) => addInput(e)}>
          <Icon name="patch-plus" />
        </Button>
      </div>
    </div>
  </Row>

  {#if currentSection === "reducers"}
    <Row>
      <Col sm="4"><label for="name">Name:</label></Col>
      <Col sm="4"><label for="name">Alias:</label></Col>
      <Col sm="4"><label for="name">Args:</label></Col>
    </Row>
  {/if}

  {#each aggregation_data[currentSection] as input, index}
    {#if currentSection === "reducers"}
      <Row>
        <Col sm="4"
          ><Input
            type="text"
            class="form-control"
            bind:value={input.name}
          /></Col
        >
        <Col sm="4"
          ><Input
            type="text"
            class="form-control"
            bind:value={input.alias}
          /></Col
        >
        <Col sm="4">
          <div class="input-group mb-2">
            <Input type="text" class="form-control" bind:value={input.args} />
            <div class="input-group-append">
                <Button
                  on:click={(e) => deleteInput(e, index)}
                  class="btn btn-danger"><Icon name="patch-minus" /></Button
                >
              </div>
          </div></Col
        >
      </Row>
    {:else}
      <Row>
        <Col sm="12">
          <div class="input-group mb-2">
            <Input type="text" class="form-control" bind:value={input} />
            <div class="input-group-append">
              <Button
                on:click={(e) => deleteInput(e, index)}
                class="btn btn-danger"><Icon name="patch-minus" /></Button
              >
            </div>
          </div>
        </Col>
      </Row>
    {/if}
  {/each}
</main>
