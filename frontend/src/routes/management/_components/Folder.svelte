<script>
  import { triggerRefreshList } from "./../_stores/trigger_refresh.js";
  import { goto, isActive } from "@roxi/routify";
  import {
    dmartCreateContent,
    dmartEntries,
    dmartFolder,
    dmartGetSchemas,
    dmartRequest,
  } from "../../../dmart.js";
  import selectedSubpath from "../_stores/selected_subpath.js";
  import { entries } from "../_stores/entries.js";
  import { contents } from "../_stores/contents.js";
  import spaces, { getSpaces } from "../_stores/spaces.js";
  import { _ } from "../../../i18n/index.js";
  import { slide } from "svelte/transition";
  import Folder from "./Folder.svelte";
  import Fa from "sveltejs-fontawesome";
  import {
    faPlusSquare,
    faTrashCan,
    faEdit,
  } from "@fortawesome/free-regular-svg-icons";
  import { toastPushFail, toastPushSuccess } from "../../../utils.js";
  import {
    Form,
    FormGroup,
    Button,
    Modal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    Label,
    Input,
  } from "sveltestrap";
  import ContentJsonEditor from "./ContentJsonEditor.svelte";

  let expanded = false;
  export let data;
  let children_subpath;

  $: {
    children_subpath = data.subpath + "/" + data.shortname;
  }
  async function toggle() {
    if (!$isActive("/management/dashboard")) {
      $goto("/management/dashboard");
    }
    selectedSubpath.set(data.uuid);
    expanded = !expanded;
    if (!$entries[children_subpath]) {
      const _entries = await dmartEntries(
        data.space_name,
        data.subpath,
        [data.resource_type],
        [],
        "search"
      );

      contents.set({
        type: "search",
        search: "",
        retrieve_attachments: true,
        space_name: data.space_name,
        subpath: data.subpath,
      });

      _entries.forEach((entry) => {
        if (entry.subpath.startsWith("/")) {
          entry.subpath = `${entry.subpath}/${entry.shortname}`;
        } else {
          entry.subpath = `/${entry.subpath}/${entry.shortname}`;
        }
      });

      data["subpaths"] = _entries
        .map((e) => {
          if (
            e.subpath.split("/").length ==
            data.subpath.split("/").length + 1
          ) {
            return e;
          }
          return null;
        })
        .filter((e) => e != null);
    }
  }

  let entryCreateModal = false;
  let modalFlag = "create";
  let createMode = "folder";
  let contentShortname = "";
  let content = {
    json: {},
    text: undefined,
  };
  let isSchemaValidated = false;
  let schemas = [];
  let selectedSchema;
  async function handleSubpathCreate() {
    modalFlag = "create";
    entryCreateModal = true;
    const r = await dmartGetSchemas(data.space_name);
    schemas = r.records.map((e) => e.shortname);
  }

  let subpathUpdateContent = { json: data, text: undefined };
  let isSubpathUpdateModalOpen = false;
  async function handleSubpathUpdate(content) {
    const record = content.json ?? JSON.parse(content.text);
    delete record.space_name;
    delete record.type;
    delete record.uuid;

    const arr = record.subpath.split("/");
    arr[arr.length - 1] = "";
    const parentSubpath = arr.join("/");

    const request = {
      space_name: data.space_name,
      request_type: "update",
      records: [{ ...record, subpath: parentSubpath }],
    };
    const response = await dmartRequest("managed/request", request);
    if (response.error) {
      alert(response.error.message);
    } else {
      toastPushSuccess();
      await getSpaces();
      isSubpathUpdateModalOpen = false;
    }
  }
  async function handleSubpathDelete() {
    // const space_name = child.shortname;
    if (
      confirm(`Are you sure want to delete ${data.shortname} subpath`) === false
    ) {
      return;
    }

    const arr = data.subpath.split("/");
    arr[arr.length - 1] = "";
    const parentSubpath = arr.join("/");

    const request = {
      space_name: data.space_name,
      request_type: "delete",
      records: [
        {
          resource_type: "folder",
          shortname: data.shortname,
          subpath: parentSubpath,
          attributes: {},
        },
      ],
    };

    const response = await dmartRequest("managed/request", request);
    if (response.status === "success") {
      toastPushSuccess();
      await getSpaces();
    } else {
      toastPushFail();
    }
  }

  let displayActionMenu = false;

  async function handleCreation(e) {
    e.preventDefault();
    if (createMode === "folder") {
      const response = await dmartFolder(
        data.space_name,
        data.subpath,
        selectedSchema,
        contentShortname
      );
      if (response.error) {
        alert(response.error.message);
      } else {
        toastPushSuccess();
        await getSpaces();
        entryCreateModal = false;
      }
    } else if (createMode === "content") {
      // if (isSchemaValidated) {
      const response = await dmartCreateContent(
        data.space_name,
        data.subpath,
        contentShortname === "" ? "auto" : contentShortname,
        selectedSchema,
        JSON.parse(content.text)
      );
      if (response.status === "success") {
        toastPushSuccess();
        triggerRefreshList.set(true);
        entryCreateModal = false;
      } else {
        toastPushFail();
      }
      // }
    }
  }
</script>

<Modal
  isOpen={entryCreateModal}
  toggle={() => {
    entryCreateModal = !entryCreateModal;
  }}
  size={"lg"}
>
  <ModalHeader />
  <Form on:submit={async (e) => await handleCreation(e)}>
    <ModalBody>
      <FormGroup>
        <Label>Type</Label>
        <Input bind:value={createMode} type="select">
          <option value="folder">Folder</option>
          <option value="content">Content</option>
        </Input>
        <Label class="mt-3">Schema</Label>
        <Input bind:value={selectedSchema} type="select">
          {#each schemas as schema}
            <option value={schema}>{schema}</option>
          {/each}
        </Input>
        {#if createMode === "content"}
          <Label class="mt-3">Shorname</Label>
          <Input placeholder="Shortname..." bind:value={contentShortname} />
          <hr />

          <Label class="mt-3">Content</Label>
          <ContentJsonEditor
            bind:content
            bind:isSchemaValidated
            handleSave={null}
          />
          <!-- onChange={handleChange}
              {validator} -->

          <hr />

          <!-- <Label>Schema</Label>
            <ContentJsonEditor
              bind:self={refJsonEditor}
              content={contentSchema}
              readOnly={true}
              mode={Mode.tree}
            /> -->
        {/if}
        {#if createMode === "folder"}
          <Label class="mt-3">Shorname</Label>
          <Input placeholder="Shortname..." bind:value={contentShortname} />
        {/if}
      </FormGroup>
    </ModalBody>
    <ModalFooter>
      <Button type="button" color="secondary" on:click={() => (open = false)}
        >cancel</Button
      >
      <Button type="submit" color="primary">Submit</Button>
    </ModalFooter>
  </Form>
</Modal>

<!-- <DynamicFormModal {props} bind:open={entryCreateModal} {handleModelSubmit} /> -->

<!-- <JsonEditorModal
  bind:open={isSubpathUpdateModalOpen}
  handleModelSubmit={handleSubpathUpdate}
  bind:content={subpathUpdateContent}
/> -->

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-mouse-events-have-key-events -->
<div
  transition:slide={{ duration: 400 }}
  class="d-flex row folder position-relative mt-1 ps-2 {$selectedSubpath ===
  data.uuid
    ? 'expanded'
    : ''}"
  on:mouseover={(e) => (displayActionMenu = true)}
  on:mouseleave={(e) => (displayActionMenu = false)}
>
  <div class="col-7" on:click={toggle}>
    {data?.attributes?.displayname?.en ?? data.shortname}
  </div>

  <div
    class="col-1"
    style="cursor: pointer;"
    hidden={!displayActionMenu}
    on:click={() => handleSubpathCreate()}
  >
    <Fa icon={faPlusSquare} size="sm" color="dimgrey" />
  </div>
  <div
    class="col-1"
    style="cursor: pointer;"
    hidden={!displayActionMenu}
    on:click={() => (isSubpathUpdateModalOpen = true)}
  >
    <Fa icon={faEdit} size="sm" color="dimgrey" />
  </div>
  <div
    class="col-1"
    style="cursor: pointer;"
    hidden={!displayActionMenu}
    on:click={async () => await handleSubpathDelete()}
  >
    <Fa icon={faTrashCan} size="sm" color="dimgrey" />
  </div>

  <span class="toolbar top-0 end-0 position-absolute px-0" />
</div>

{#if data.subpaths}
  {#each data.subpaths as subapth (subapth.shortname + subapth.uuid)}
    <div
      hidden={!expanded}
      style="padding-left: 5px;"
      transition:slide={{ duration: 400 }}
    >
      <Folder data={{ space_name: data.space_name, ...subapth }} />
    </div>
  {/each}
{/if}

<!-- {#if expanded && $entries[children_subpath]}
  <ul class="py-1 ps-1 ms-2 border-start">
    {#each $entries[children_subpath] as child (children_subpath + child.data.shortname)}
      <li>
        {#if child.data.resource_type === "folder"}
          <svelte:self data={child.data} />
        {:else}
          <File data={child.data} />
        {/if}
      </li>
    {/each}
  </ul>
{/if} -->
<style>
  ul {
    /*padding: 0.2em 0 0 0.5em;
    margin: 0 0 0 0.5em;*/
    list-style: none;
    /*border-left: 1px solid #eee;*/
  }

  .folder {
    /*font-weight: bold;*/
    cursor: pointer;
    display: list-item;
    list-style: none;
    border-top: thin dotted grey;
  }

  .folder:hover {
    z-index: 2;
    color: #495057;
    text-decoration: none;
    background-color: #e8e9ea;
  }

  .expanded {
    background-color: #e8e9ea;
    border-bottom: thin dotted green;
  }

  .toolbar {
    display: none;
    color: brown;
  }

  .folder:hover .toolbar {
    display: flex;
  }
</style>
