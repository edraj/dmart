<script lang="ts">
  import { goto, params } from "@roxi/routify";
  $goto
  import {
    ListGroup,
    ListGroupItem,
    Modal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    Button,
  } from "sveltestrap";
  import "bootstrap";
  import { ResourceType, retrieve_entry } from "@/dmart";
  import BreadCrumbLite from "@/components/management/BreadCrumbLite.svelte";

  type ModalData = {
    subpath: string;
    shortname: string;
    resource_type: ResourceType;
    uuid: string;
    issues: [];
    exception: string;
  };
  let modalData: ModalData = $state({
    subpath: "",
    shortname: "",
    resource_type: ResourceType.content,
    uuid: "",
    issues: [],
    exception: "",
  });

  function handleEdit() {    
    $goto(
      `/management/content/[space_name]/[subpath]/[shortname]/[resource_type]`,
      {
        space_name: $params.shortname,
        subpath: modalData.subpath.replaceAll('/','-'),
        shortname: modalData.shortname,
        resource_type: modalData.resource_type,
        validate_schema: "false",
      }
    );
  }

  let open = $state(false);
  let isEntryExist = $state(false);
  async function handleErrorEntryClick(err_entry: ModalData, extra: any) {
    modalData = { ...err_entry, ...extra };

    try {
      await retrieve_entry(modalData.resource_type, $params.space_name, $params.subpath.replaceAll("-", "/"), $params.shortname, false, false,false)
      isEntryExist = true      
    } catch (error) {
      isEntryExist = false
    }

    open = true;
  }

  const toggleModal = () => {open != open}

</script>

<Modal isOpen={open} toggle={toggleModal} size={"lg"}>
<!--  <ModalHeader toggle={toggleModal}>{modalData.shortname}</ModalHeader>-->
  <h5 class="modal-header modal-title">{modalData.shortname}</h5>
  <ModalBody>
    <p><b>UUID:</b> {modalData.uuid}</p>
    <p><b>Space name:</b> {$params.shortname}</p>
    <p><b>Subpath:</b> {modalData.subpath}</p>
    <p><b>Issues:</b> {modalData.issues}</p>
    <p><b>Exception:</b><br /> {modalData.exception}</p>
  </ModalBody>
  <ModalFooter style="justify-content: space-between;">
    <Button color="secondary" onclick={() => (open = false)}>Close</Button>
    {#if isEntryExist}
    <Button color="primary" onclick={handleEdit}>Edit</Button>
    {:else}
    <Button color="warning">Entry does not exist</Button>
    {/if}
  </ModalFooter>
</Modal>

<BreadCrumbLite
  space_name={"management"}
  subpath={"health_check"}
  resource_type={ResourceType.content}
  schema_name={"health_check"}
  shortname={$params.shortname}
/>

<div class="mx-2 mt-3 mb-3"></div>
{#if $params.shortname}
  {#key $params.shortname}
    {#await retrieve_entry(ResourceType.content, "management", "health_check/", $params.shortname, true, true)}
      <p>Fetching...</p>
    {:then response}
      <ListGroup>
        {#if response.payload.body["invalid_folders"]}
          <ListGroupItem active>
            {`Invalid folders (${response.payload.body["invalid_folders"].length} invalid entires)`}
          </ListGroupItem>
          {#if response.payload.body["invalid_folders"].length}
            {#each response.payload.body["invalid_folders"] as entry}
              <ListGroupItem color={"secondary"}>{entry}</ListGroupItem>
            {/each}
          {/if}
        {/if}

        <ListGroupItem active>
          {`Folders report`}
        </ListGroupItem>
        {#if response.payload.body["folders_report"]}
          {#each Object.keys(response.payload.body["folders_report"]) as key_entry}
            <ListGroupItem color={"secondary"}>{key_entry}</ListGroupItem>
            {#if response.payload.body["folders_report"][key_entry].valid_entries}
              <ListGroupItem color={"success"}
                >{`Valid entries ${response.payload.body["folders_report"][key_entry].valid_entries}`}</ListGroupItem
              >
            {/if}
            {#if response.payload.body["folders_report"][key_entry].invalid_entries}
              <ListGroupItem color={"danger"}
                >{`Invalid entries ${response.payload.body["folders_report"][key_entry].invalid_entries.length}`}</ListGroupItem
              >
              {#each response.payload.body["folders_report"][key_entry].invalid_entries as err_entry}
                <ListGroupItem
                style={"cursor: pointer;"}
                  onclick={() => {
                    handleErrorEntryClick(err_entry, { subpath: key_entry });
                  }}>{err_entry.shortname}</ListGroupItem
                >
              {/each}
            {/if}
          {/each}
        {/if}
        {#if response.payload.body["invalid_meta_folders"]}
          <ListGroupItem active>
            {`Invalid meta folders (${response.payload.body["invalid_meta_folders"].length} invalid entires)`}
          </ListGroupItem>
          {#if response.payload.body["invalid_meta_folders"].length}
            {#each response.payload.body["invalid_meta_folders"] as entry}
              <ListGroupItem color={"secondary"}>{entry}</ListGroupItem>
            {/each}
          {/if}
        {/if}
      </ListGroup>
    {:catch error}
      <p style="color: red">{error.message}</p>
    {/await}
  {/key}
{/if}
