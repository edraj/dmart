<script>
  import {
    triggerRefreshList,
    triggerSearchList,
  } from "./../_stores/trigger_refresh.js";
  import {
    dmartManContent,
    dmartEntries,
    dmartCreateFolder,
    dmartGetSchemas,
    dmartRequest,
    dmartMoveFolder,
  } from "../../../dmart.js";
  import selectedSubpath from "../_stores/selected_subpath.js";
  import { entries } from "../_stores/entries.js";
  import spaces from "../_stores/spaces.js";
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
  import { Mode } from "svelte-jsoneditor";

  let expanded = false;
  export let data;
  export let parent_data;
  let folderContent = { json: {}, text: undefined };

  async function updateList(event = "create") {
    const idxSpace = $spaces.children.findIndex(
      (child) => child.shortname === data.space_name
    );
    let r = $spaces.children[idxSpace];
    const s = data.subpath.replace("/", "").split("/");

    if (event === "create") {
      const _entries = await dmartEntries(
        data.space_name,
        data.subpath,
        [data.resource_type],
        [],
        "search"
      );
      if (_entries.length === 0) {
        return;
      }

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
            e.subpath.split("/").length ===
            data.subpath.split("/").length + 1
          ) {
            return e;
          }
          return null;
        })
        .filter((e) => e != null);
      s.forEach((subpath) => {
        const idx = r.subpaths.findIndex(
          (child) => child.shortname === subpath
        );
        r = r.subpaths[idx];
      });

      r["subpaths"] = _entries;
      r["subpath"] = data.subpath;
    } else if (event === "delete") {
      r = r.subpaths;
      s.pop();
      s.forEach((subpath) => {
        const idx = r.findIndex((child) => child.shortname === subpath);
        r = r[idx].subpaths;
      });
      const idx = r.findIndex((child) => child.shortname === data.shortname);
      r.splice(idx, 1);
      parent_data.subpaths = r;
    }
    spaces.set({
      ...$spaces,
      children: $spaces.children,
    });
  }

  async function toggle() {
    triggerSearchList.set("");
    selectedSubpath.set(data.uuid);
    expanded = !expanded;
    if (!$entries[data.shortname]) {
      await updateList();
    }
    let subpath = data.subpath;
    if (subpath.startsWith("/")) {
      subpath = subpath.substring(1);
    }
    subpath = subpath.replaceAll("/", "-");
    window.history.replaceState(
      history.state,
      "",
      `/management/dashboard/${data.space_name}/${subpath}`
    );
  }

  let entryCreateModal = false;
  let modalFlag = "create";
  let entryType = "folder";
  let contentShortname = "";
  let content = {
    json: {},
    text: undefined,
  };
  let isSchemaValidated = false;
  let schemas = [];
  let selectedSchema;

  async function handleSubpathMan(flag) {
    modalFlag = flag;
    const r = await dmartGetSchemas(data.space_name);
    schemas = r.records.map((e) => e.shortname);
    if (flag === "update") {
      contentShortname = data.shortname;
      const d = { ...data };
      delete d.shortname;
      delete d.subpath;
      delete d.type;
      delete d.subpaths;
      delete d.attachments;
      delete d.attributes.created_at;
      delete d.attributes.updated_at;
      folderContent.json = d;
    }
    entryCreateModal = true;
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
      updateList("delete");
    } else {
      toastPushFail();
    }
  }

  let displayActionMenu = false;

  async function handleSubmit(e) {
    e.preventDefault();
    let response;
    if (entryType === "folder") {
      if (modalFlag === "create") {
        response = await dmartCreateFolder(
          data.space_name,
          data.subpath,
          selectedSchema,
          contentShortname
        );
      } else if (modalFlag === "update") {
        const i = data.subpath.lastIndexOf("/");
        const _subpath = data.subpath.substring(0, i);
        if (data.shortname !== contentShortname)
          response = await dmartMoveFolder(
            data.space_name,
            _subpath,
            data.shortname,
            contentShortname
          );
      }
    } else if (entryType === "content") {
      const body = content.json
        ? { ...content.json }
        : JSON.parse(content.text);
      response = await dmartManContent(
        data.space_name,
        data.subpath,
        contentShortname === "" ? "auto" : contentShortname,
        selectedSchema,
        body,
        modalFlag
      );
    }
    if (response.status === "success") {
      toastPushSuccess();
      triggerRefreshList.set(true);
      entryCreateModal = false;
      contentShortname = "";
      await updateList();
    } else {
      toastPushFail();
    }
  }

  async function handleFolderUpdate() {
    const payload = folderContent.json
      ? { ...folderContent.json }
      : JSON.parse(folderContent.text);

    const arr = data.subpath.split("/");
    arr[arr.length - 1] = "";
    const parentSubpath = arr.join("/");

    const request = {
      space_name: data.space_name,
      request_type: "update",
      records: [
        {
          ...payload,
          shortname: data.shortname,
          subpath: parentSubpath,
        },
      ],
    };
    const response = await dmartRequest("managed/request", request);
    if (response.status === "success") {
      data = { ...data, ...payload };
      toastPushSuccess();
    } else {
      toastPushFail();
    }
  }
</script>

<Modal
  isOpen={entryCreateModal}
  toggle={() => {
    entryCreateModal = !entryCreateModal;
    contentShortname = "";
  }}
  size={"lg"}
>
  <ModalHeader />
  <Form on:submit={async (e) => await handleSubmit(e)}>
    <ModalBody>
      <FormGroup>
        {#if modalFlag === "create"}
          <Label>Type</Label>
          <Input bind:value={entryType} type="select">
            <option value="folder">Folder</option>
            <option value="content">Content</option>
          </Input>
          <Label class="mt-3">Schema</Label>
          <Input bind:value={selectedSchema} type="select">
            <option value={""}>{"None"}</option>
            {#each schemas as schema}
              <option value={schema}>{schema}</option>
            {/each}
          </Input>
        {/if}
        {#if entryType === "content" && modalFlag === "create"}
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
        {#if entryType === "folder"}
          <Label class="mt-3">Shortname</Label>
          <Input
            placeholder="Shortname..."
            bind:value={contentShortname}
            required
          />
          {#if modalFlag === "update"}
            <Label class="mt-3">Content</Label>
            <ContentJsonEditor
              bind:content={folderContent}
              handleSave={async () => handleFolderUpdate()}
              mode={Mode.tree}
            />
          {/if}
        {/if}
      </FormGroup>
    </ModalBody>
    <ModalFooter>
      <Button
        type="button"
        color="secondary"
        on:click={() => {
          entryCreateModal = false;
          contentShortname = "";
        }}>cancel</Button
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
  class="d-flex row justify-content-between folder position-relative mt-1 ps-2 
  {$selectedSubpath === data.uuid ? 'expanded' : ''}"
  on:mouseover={(e) => (displayActionMenu = true)}
  on:mouseleave={(e) => (displayActionMenu = false)}
  on:click={toggle}
>
  <div class="col-12" style="overflow-wrap: anywhere;">
    {data?.attributes?.displayname?.en ?? data.shortname}
  </div>

  <div
    class="d-flex col justify-content-end"
    style="position: absolute;z-index: 1;"
  >
    <div
      style="cursor: pointer;background-color: #e8e9ea;"
      hidden={!displayActionMenu}
      on:click={(event) => {
        event.stopPropagation();
        handleSubpathMan("create");
      }}
    >
      <Fa icon={faPlusSquare} size="sm" color="dimgrey" />
    </div>
    <div
      class="px-1"
      style="cursor: pointer;background-color: #e8e9ea;"
      hidden={!displayActionMenu}
      on:click={(event) => {
        event.stopPropagation();
        handleSubpathMan("update");
      }}
    >
      <Fa icon={faEdit} size="sm" color="dimgrey" />
    </div>
    <div
      style="cursor: pointer;background-color: #e8e9ea;"
      hidden={!displayActionMenu}
      on:click={async (event) => {
        event.stopPropagation();
        await handleSubpathDelete();
      }}
    >
      <Fa icon={faTrashCan} size="sm" color="dimgrey" />
    </div>
  </div>
</div>

{#if data.subpaths}
  {#each data.subpaths as subpath (subpath.shortname + subpath.uuid)}
    <div
      hidden={!expanded}
      style="padding-left: 5px;"
      transition:slide={{ duration: 400 }}
    >
      <Folder
        data={{ space_name: data.space_name, ...subpath }}
        bind:parent_data={data}
      />
    </div>
  {/each}
{/if}

<style>
  .folder {
    /*font-weight: bold;*/
    cursor: pointer;
    display: list-item;
    list-style: none;
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
</style>
