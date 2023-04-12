<script>
  import { Circle2 } from "svelte-loading-spinners";
  import { dmartHealthCheck } from "../../../dmart";
  import spaces from "../_stores/spaces";
  import { Label, ListGroup, ListGroupItem, Input } from "sveltestrap";
  import "bootstrap";
  import { toastPushFail } from "../../../utils";
  import { triggerSidebarSelection } from "../_stores/triggers";

  let isLoading;
  let subpaths = {};
  $: {
    async function updateSpaceHealthCheck() {
      isLoading = true;
      const response = await dmartHealthCheck($triggerSidebarSelection);
      isLoading = false;
      if (response.status === "success") {
        subpaths = response.attributes.folders_report;
      } else {
        toastPushFail();
      }
    }
    if ($triggerSidebarSelection) {
      updateSpaceHealthCheck();
    }
  }
</script>

<div class="mx-2 mt-3 mb-3">
  <Label for="exampleSelect">Space name</Label>
  <Input type="select" on:change={async (e) => await handleChange(e)}>
    <option value={""}> - Select Space - </option>
    {#each $spaces.children as space}
      <option value={space.shortname}>
        {space.shortname}
      </option>
    {/each}
  </Input>
</div>
{#if isLoading}
  <div class="d-flex justify-content-center mt-3">
    <Circle2 size="200" unit="px" duration="1s" />
  </div>
{/if}
{#if !isLoading}
  {#if Object.keys(subpaths).length === 0}
    <ListGroupItem color="dark" class="mx-2 px-3 py-3 text-center"
      >Nothing to display</ListGroupItem
    >
  {/if}
  {#each Object.keys(subpaths) as subpath}
    <ListGroup>
      <ListGroupItem active
        >{subpath} ({subpaths[subpath]?.valid_entries ??
          subpaths[subpath].invalid_entries.length.toString() + " corrupted"} entry)</ListGroupItem
      >
      {#if subpaths[subpath].invalid_entries}
        {#each subpaths[subpath].invalid_entries as entry}
          <ListGroupItem
            href={`/management/dashboard/${$triggerSidebarSelection}/${subpath.replaceAll(
              "/",
              "-"
            )}/${entry}`}
            action>{entry}</ListGroupItem
          >
        {/each}
      {/if}
    </ListGroup>
  {/each}
{/if}
