<script lang="ts">
  import { onDestroy } from "svelte";
  import {
    QueryType,
    RequestType,
    ResourceType,
    ActionResponse,
    Status,
    query,
    request,
    ResponseEntry,
    space,
  } from "@/dmart";
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
      Nav,
      ButtonGroup, TabContent, TabPane,
  } from "sveltestrap";
  import Icon from "../../Icon.svelte";
  import { _ } from "@/i18n";
  import ListView from "../ListView.svelte";
  import Prism from "../../Prism.svelte";
  import { JSONEditor, Mode } from "svelte-jsoneditor";
  import { status_line } from "@/stores/management/status_line";
  import { showToast, Level } from "@/utils/toast";
  import { faSave } from "@fortawesome/free-regular-svg-icons";
  import refresh_spaces from "@/stores/management/refresh_spaces";
  import { isDeepEqual, removeEmpty } from "@/utils/compare";
  import Table2Cols from "@/components/management/Table2Cols.svelte";


  let header_height: number;
  export let space_name: string;

  export let current_space: ResponseEntry;
  let content = { json: current_space || {}, text: undefined };
  let oldContent = { json: current_space || {}, text: undefined };
  let entryContent = { json: current_space || {}, text: undefined };

  let tab_option = "list";

  onDestroy(() => status_line.set(""));
  status_line.set("none FIXME");

  // let isSchemaValidated: boolean;
  // function handleChange(updatedContent, previousContent, patchResult) {
  // const v = patchResult?.contentErrors?.validationErrors;
  // isSchemaValidated =  (v === undefined || v.length === 0)
  //}

  let errorContent = null;
  async function handleSave() {
    // if (!isSchemaValidated) {
    //   alert("The content does is not validated agains the schema");
    //   return;
    // }
    errorContent = null;
    const data = content.json
      ? structuredClone(content.json)
      : JSON.parse(content.text);
    const response = await space({
      space_name: current_space.shortname,
      request_type: RequestType.update,
      records: [
        {
          resource_type: ResourceType.space,
          shortname: current_space.shortname,
          subpath: "/",
          attributes: data,
        },
      ],
    });
    if (response.status == Status.success) {
      showToast(Level.info);
      oldContent = structuredClone(content);
    } else {
      errorContent = response;
      showToast(Level.warn);
    }
  }

  function handleRenderMenu(items: Array<any>, context) {
    items = items.filter(
        (item) => !["tree", "text", "table"].includes(item.text)
    );

    const separator = {
      separator: true,
    };

    const saveButton = {
      onClick: handleSave,
      icon: faSave,
      title: "Save",
    };

    const itemsWithoutSpace = items.slice(0, items.length - 2);
    return itemsWithoutSpace.concat([
      separator,
      saveButton,
      {
        space: true,
      },
    ]);
  }

  let isModalOpen = false;
  let modalFlag = "create";
  let entryType = "folder";
  let contentShortname = "";
  let selectedSchema = "";
  let new_resource_type: ResourceType = ResourceType.content;

  async function handleSubmit(event: Event) {
    event.preventDefault();
    let response: ActionResponse;
    if (entryType === "content") {
      const body = entryContent.json
        ? structuredClone(entryContent.json)
        : JSON.parse(entryContent.text);
      const request_body = {
        space_name: current_space.shortname,
        request_type: RequestType.create,
        records: [
          {
            resource_type: new_resource_type,
            shortname: contentShortname === "" ? "auto" : contentShortname,
            subpath: "/",
            attributes: {
              is_active: true,
              payload: {
                content_type: "json",
                schema_shortname: selectedSchema ? selectedSchema : "",
                body,
              },
            },
          },
        ],
      };
      response = await request(request_body);
    } else if (entryType === "folder") {
      const request_body = {
        space_name: current_space.shortname,
        request_type: RequestType.create,
        records: [
          {
            resource_type: ResourceType.folder,
            shortname: contentShortname === "" ? "auto" : contentShortname,
            subpath: "/",
            attributes: {
              is_active: true,
            },
          },
        ],
      };
      response = await request(request_body);
    }
    if (response.status === "success") {
      showToast(Level.info);
      contentShortname = "";
      isModalOpen = false;
      refresh_spaces.refresh();
    } else {
      showToast(Level.warn);
    }
  }

  async function handleDelete() {
    if (
      confirm(
        `Are you sure want to delete ${current_space.shortname} space`
      ) === false
    ) {
      return;
    }
    const request_body = {
      space_name: current_space.shortname,
      request_type: RequestType.delete,
      records: [
        {
          resource_type: ResourceType.space,
          shortname: current_space.shortname,
          subpath: "/",
          branch_name: "master",
          attributes: {},
        },
      ],
    };
    const response = await space(request_body);
    if (response.status === "success") {
      showToast(Level.info);
      refresh_spaces.refresh();
      history.go(-1);
    } else {
      showToast(Level.warn);
    }
  }

  function beforeUnload(event: Event) {
    if (!isDeepEqual(removeEmpty(content), removeEmpty(oldContent))) {
      event.preventDefault();
      if (
        confirm("You have unsaved changes, do you want to leave ?") === false
      ) {
        return false;
      }
    }
  }
  const toggelModal = () => {
    isModalOpen = !isModalOpen;
    contentShortname = "";
  };
</script>

<svelte:window on:beforeunload={beforeUnload} />

<Modal isOpen={isModalOpen} toggle={toggelModal} size={"lg"}>
  <ModalHeader toggle={toggelModal} />
  <Form on:submit={async (e) => await handleSubmit(e)}>
    <ModalBody>
      <FormGroup>
        {#if modalFlag === "create"}
          <Label class="mt-3">Resource type</Label>
          <Input bind:value={new_resource_type} type="select">
            {#each Object.values(ResourceType) as type}
              <option value={type}>{type}</option>
            {/each}
          </Input>
          <Label class="mt-3">Schema</Label>
          <Input bind:value={selectedSchema} type="select">
            <option value={""}>{"None"}</option>
            {#await query( { space_name: current_space.shortname, type: QueryType.search, subpath: "/schema", search: "", retrieve_json_payload: true, limit: 99 } ) then schemas}
              {#each schemas.records.map((e) => e.shortname) as schema}
                <option value={schema}>{schema}</option>
              {/each}
            {/await}
          </Input>
        {/if}
        {#if entryType === "content" && modalFlag === "create"}
          <Label class="mt-3">Shortname</Label>
          <Input placeholder="Shortname..." bind:value={contentShortname} />
          <hr />

          <Label class="mt-3">Content</Label>
          <JSONEditor
            onRenderMenu={handleRenderMenu}
            mode={Mode.text}
            bind:content={entryContent}
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
          {/if}
        {/if}
      </FormGroup>
    </ModalBody>
    <ModalFooter>
      <Button
        type="button"
        color="secondary"
        on:click={() => {
          isModalOpen = false;
          contentShortname = "";
        }}>cancel</Button
      >
      <Button type="submit" color="primary">Submit</Button>
    </ModalFooter>
  </Form>
</Modal>

<div bind:clientHeight={header_height} class="pt-3 pb-2 px-2">
  <div class="d-flex justify-content-end w-100">
    <ButtonGroup size="sm" class="align-items-center">
      <span class="font-monospace">
        <small>
          <span class="text-success">{space_name}</span> :
          <strong>{current_space.shortname}</strong>
          ({ResourceType.space})
        </small>
      </span>
    </ButtonGroup>
    <ButtonGroup size="sm" class="ms-auto align-items-center">
      <span class="ps-2 pe-1"> {$_("views")} </span>
      <Button
        outline
        color="success"
        size="sm"
        class="justify-content-center text-center py-0 px-1"
        active={"list" === tab_option}
        title={$_("list")}
        on:click={() => (tab_option = "list")}
      >
        <Icon name="card-list" />
      </Button>

      <Button
        outline
        color="success"
        size="sm"
        class="justify-content-center text-center py-0 px-1"
        active={"view" === tab_option}
        title={$_("view")}
        on:click={() => (tab_option = "view")}
      >
        <Icon name="binoculars" />
      </Button>
      <Button
        outline
        color="success"
        size="sm"
        class="justify-content-center text-center py-0 px-1"
        active={"edit" === tab_option}
        title={$_("edit")}
        on:click={() => (tab_option = "edit")}
      >
        <Icon name="pencil" />
      </Button>
    </ButtonGroup>
    <ButtonGroup size="sm" class="align-items-center">
      <span class="ps-2 pe-1"> {$_("actions")} </span>
      <Button
        outline
        color="success"
        size="sm"
        title={$_("delete")}
        on:click={handleDelete}
        class="justify-content-center text-center py-0 px-1"
      >
        <Icon name="trash" />
      </Button>
    </ButtonGroup>
    <Button
            outline
            color="success"
            size="sm"
            title={$_("create_entry")}
            class="justify-contnet-center text-center py-0 px-1"
            on:click={() => {
              entryType = "content";
              isModalOpen = true;
            }}
    >
      <Icon name="file-plus" />
    </Button>
    <Button
            outline
            color="success"
            size="sm"
            title={$_("create_folder")}
            class="justify-contnet-center text-center py-0 px-1"
            on:click={() => {
                entryType = "folder";
                new_resource_type = ResourceType.folder;
                isModalOpen = true;
              }}
    >
      <Icon name="folder-plus" />
    </Button>
  </div>
</div>
<div
  class="px-1 tab-content"
  style="height: calc(100% - {header_height}px); overflow: hidden auto;"
>
  <div class="tab-pane" class:active={tab_option === "list"}>
    {#if tab_option === "list"}
      {#key current_space}
        <ListView space_name={current_space.shortname} subpath={"/"} />
      {/key}
    {:else}
      <h1>This should not be displayed {tab_option}</h1>
    {/if}
  </div>
  <div class="tab-pane" class:active={tab_option === "source"}>
    <!--JSONEditor json={entry} /-->
    <div
      class="px-1 pb-1 h-100"
      style="text-align: left; direction: ltr; overflow: hidden auto;"
    >
      <pre>
        {JSON.stringify(current_space, undefined, 1)}
      </pre>
    </div>
  </div>
  <div class="tab-pane" class:active={tab_option === "view"}>
    <div
      class="px-1 pb-1 h-100"
      style="text-align: left; direction: ltr; overflow: hidden auto;"
    >
      <TabContent>
        <TabPane tabId="table" tab="Table" active><Table2Cols entry={current_space} /></TabPane>
        <TabPane tabId="form" tab="Raw">
          <Prism code={current_space} />
        </TabPane>
      </TabContent>
    </div>
  </div>
  <div class="tab-pane" class:active={tab_option === "edit"}>
    <div
      class="px-1 pb-1 h-100"
      style="text-align: left; direction: ltr; overflow: hidden auto;"
    >
      {#if tab_option === "edit"}
        <JSONEditor
          bind:content
          onRenderMenu={handleRenderMenu}
          mode={Mode.text}
        />
        {#if errorContent}
          <h3 class="mt-3">Error:</h3>
          <Prism bind:code={errorContent} />
        {/if}
      {/if}
    </div>
  </div>
</div>

<style>
  span {
    color: dimgrey;
  }
</style>
