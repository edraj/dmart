<script>
  import { Circle2 } from "svelte-loading-spinners";
  import { dmartHealthCheck } from "../../../dmart";
  import spaces from "../_stores/spaces";
  import { Label, ListGroup, ListGroupItem, Input } from "sveltestrap";
  import "bootstrap";
  import { toastPushFail } from "../../../utils";

  let selectedSpaceName;
  let subpaths = {};

  async function handleChange() {
    if (selectedSpaceName === "") {
      return;
    }
    const response = await dmartHealthCheck(selectedSpaceName);
    if (response.status === "success") {
      subpaths = response.attributes.folders_report;
    } else {
      toastPushFail();
    }
  }
</script>

<div class="mx-2 mt-3 mb-3  ">
  <Label for="exampleSelect">Space name</Label>
  <Input
    type="select"
    bind:value={selectedSpaceName}
    on:change={async () => await handleChange()}
  >
    <option value={""}> - Select Space - </option>
    {#each $spaces.children as space}
      <option value={space.shortname}>
        {space.shortname}
      </option>
    {/each}
  </Input>
</div>

{#each Object.keys(subpaths) as subpath}
  <ListGroup>
    <ListGroupItem active
      >{subpath} ({subpaths[subpath]?.valid_entries ??
        subpaths[subpath].invalid_entries.length.toString() + " corrupted"} entry)</ListGroupItem
    >
    {#if subpaths[subpath].invalid_entries}
      {#each subpaths[subpath].invalid_entries as entry}
        <ListGroupItem
          href={`/management/${selectedSpaceName}/${subpath}/${entry}`}
          action>{entry}</ListGroupItem
        >
      {/each}
    {/if}
  </ListGroup>
{/each}
