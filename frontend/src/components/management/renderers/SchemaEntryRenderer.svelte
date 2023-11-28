<script lang="ts">
  import { faSave } from "@fortawesome/free-regular-svg-icons";
  import Prism from "@/components/Prism.svelte";
  import {
    QueryType,
    RequestType,
    ResourceType,
    ResponseEntry,
    Status,
    get_spaces,
    request,
  } from "@/dmart";
  import { Level, showToast } from "@/utils/toast";
  import { JSONEditor, Mode } from "svelte-jsoneditor";
  import { Button, Nav, ButtonGroup } from "sveltestrap";
  import Icon from "../../Icon.svelte";
  import Attachments from "../Attachments.svelte";
  import ListView from "../ListView.svelte";
  import { _ } from "@/i18n";
  import { isDeepEqual, removeEmpty } from "@/utils/compare";
  import history_cols from "@/stores/management/list_cols_history.json";
  import SchemaEditor, {
    transformToProperBodyRequest,
  } from "../editors/SchemaEditor.svelte";
  import BreadCrumbLite from "../BreadCrumbLite.svelte";
  import { generateUUID } from "@/utils/uuid";
  import { onMount } from "svelte";
  import { goto } from "@roxi/routify";

  let header_height: number;

  export let entry: ResponseEntry = null;
  export let space_name: string = null;
  export let shortname: string = null;

  const subpath = "/schema";
  const schema_name = "meta_schema";
  const resource_type: ResourceType = ResourceType.schema;
  let tab_option = "view";

  let contentMeta = { json: {}, text: undefined };
  let oldContentMeta = { json: {}, text: undefined };
  let content = {
    json: {},
    text: undefined,
  };
  let oldContent = { json: {}, text: undefined };
  onMount(async () => {
    const cpy = JSON.parse(JSON.stringify(entry));
    delete cpy?.payload?.body;
    contentMeta.json = cpy;
    contentMeta = structuredClone(contentMeta);
    oldContentMeta = structuredClone(contentMeta);
  });
  let items: any = [
    {
      id: generateUUID(),
      name: "root",
      type: "object",
      title: "title",
      description: "",
    },
  ];

  let selected_space;
  let spaces = [];
  onMount(() => {
    (async () => {
      spaces = (await get_spaces()).records;
      selected_space = space_name;
    })();

    if (entry !== null) {
      const _items = entry.payload.body as any;
      items[0] = transformEntryToRender(_items);
      items[0].name = "root";
    }
  });

  function transformEntryToRender(entries) {
    if (entries.properties) {
      const properties = [];
      Object.keys(entries.properties).forEach((entry) => {
        const id = generateUUID();
        if (entries?.properties[entry]?.properties) {
          properties.push({
            id,
            name: entry,
            ...transformEntryToRender(entries.properties[entry]),
          });
        } else {
          properties.push({
            id,
            name: entry,
            ...entries.properties[entry],
          });
        }
      });
      entries.properties = properties;
    }
    return entries;
  }

  function handleRenderMenu(items: any, _context: any) {
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

  let schema_shortname = shortname;
  let errorContent = null;

  async function handleSave(e: Event) {
    e.preventDefault();

    errorContent = null;

    let data: any = contentMeta.json
      ? structuredClone(contentMeta.json)
      : JSON.parse(contentMeta.text);
    data.payload.body = entry.payload;

    const request_data = {
      space_name: space_name,
      request_type: RequestType.replace,
      records: [
        {
          resource_type,
          shortname: entry.shortname,
          subpath,
          attributes: data,
        },
      ],
    };

    const response = await request(request_data);
    if (response.status == Status.success) {
      showToast(Level.info);
      oldContentMeta = structuredClone(contentMeta);

      if (data.shortname !== entry.shortname) {
        const moveAttrb = {
          src_subpath: subpath,
          src_shortname: entry.shortname,
          dest_subpath: subpath,
          dest_shortname: data.shortname,
        };
        const response = await request({
          space_name: space_name,
          request_type: RequestType.move,
          records: [
            {
              resource_type,
              shortname: entry.shortname,
              subpath,
              attributes: moveAttrb,
            },
          ],
        });
        if (response.status == Status.success) {
          showToast(Level.info);
        } else {
          errorContent = response;
          showToast(Level.warn);
        }
      }

      window.location.reload();
    } else {
      errorContent = response;
      showToast(Level.warn);
    }
  }

  async function handleSaveContent(e) {
    e.preventDefault();

    errorContent = null;

    let body = content.json
      ? structuredClone(content.json)
      : JSON.parse(content.text);
    body = transformToProperBodyRequest(body);
    body = body[0];
    delete body.name;

    const request_body = {
      space_name: selected_space,
      request_type: RequestType.update,
      records: [
        {
          resource_type: ResourceType.schema,
          shortname: schema_shortname,
          subpath: subpath,
          attributes: {
            is_active: true,
            payload: {
              content_type: "json",
              schema_shortname: "meta_schema",
              body,
            },
          },
        },
      ],
    };
    const response = await request(request_body);

    if (response.status == Status.success) {
      showToast(Level.info);
      oldContent = structuredClone(content);
    } else {
      errorContent = response;
      showToast(Level.warn);
    }
  }

  async function handleDelete() {
    if (
      confirm(`Are you sure want to delete ${entry.shortname} entry`) === false
    ) {
      return;
    }

    let targetSubpath: string;
    if (resource_type === ResourceType.folder) {
      const arr = subpath.split("/");
      arr[arr.length - 1] = "";
      targetSubpath = arr.join("/");
    } else {
      targetSubpath = subpath;
    }

    const request_body = {
      space_name,
      request_type: RequestType.delete,
      records: [
        {
          resource_type,
          shortname: entry.shortname,
          subpath: targetSubpath || "/",
          branch_name: "master",
          attributes: {},
        },
      ],
    };
    const response = await request(request_body);
    if (response.status === "success") {
      showToast(Level.info);
      history.go(-1);
    } else {
      showToast(Level.warn);
    }
  }

  function beforeUnload(event: Event) {
    if (
      !isDeepEqual(removeEmpty(contentMeta), removeEmpty(oldContentMeta)) &&
      !isDeepEqual(removeEmpty(content), removeEmpty(oldContent))
    ) {
      event.preventDefault();
      if (
        confirm("You have unsaved changes, do you want to leave ?") === false
      ) {
        return false;
      }
    }
  }
</script>

<svelte:window on:beforeunload={beforeUnload} />

<div bind:clientHeight={header_height} class="pt-3 pb-2 px-2">
  <Nav class="w-100">
    <BreadCrumbLite
      {space_name}
      {subpath}
      {resource_type}
      {schema_name}
      shortname={entry.shortname}
    />
    <ButtonGroup size="sm" class="ms-auto align-items-center">
      <span class="ps-2 pe-1"> {$_("views")} </span>

      <Button
        outline
        color="success"
        size="sm"
        class="justify-content-center text-center py-0 px-1"
        active={"view" == tab_option}
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
        active={"edit_meta" == tab_option}
        title={$_("edit") + " meta"}
        on:click={() => (tab_option = "edit_meta")}
      >
        <Icon name="code-slash" />
      </Button>
      {#if entry.payload}
        <Button
          outline
          color="success"
          size="sm"
          class="justify-content-center text-center py-0 px-1"
          active={"edit_content" == tab_option}
          title={$_("edit") + " payload"}
          on:click={() => (tab_option = "edit_content")}
        >
          <Icon name="pencil" />
        </Button>
      {/if}
      <Button
        outline
        color="success"
        size="sm"
        class="justify-content-center text-center py-0 px-1"
        active={"attachments" == tab_option}
        title={$_("attachments")}
        on:click={() => (tab_option = "attachments")}
      >
        <Icon name="paperclip" />
      </Button>
      <Button
        outline
        color="success"
        size="sm"
        class="justify-content-center text-center py-0 px-1"
        active={"history" == tab_option}
        title={$_("history")}
        on:click={() => (tab_option = "history")}
      >
        <Icon name="clock-history" />
      </Button>
    </ButtonGroup>
    <ButtonGroup size="sm" class="align-items-center">
      <span class="ps-2 pe-1"> {$_("actions")} </span>
      {#if tab_option === "edit_content"}
        <Button
          outline
          color="success"
          size="sm"
          title={$_("save")}
          on:click={handleSaveContent}
          class="justify-content-center text-center py-0 px-1"
        >
          <Icon name="cloud-upload" />
        </Button>
      {/if}
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
  </Nav>
</div>
<div
  class="px-1 tab-content"
  style="height: calc(100% - {header_height}px); overflow: hidden auto;"
>
  <div class="tab-pane" class:active={tab_option === "list"}>
    <ListView {space_name} {subpath} />
  </div>
  <div class="tab-pane" class:active={tab_option === "source"}>
    <!--JSONEditor json={entry} /-->
    <div
      class="px-1 pb-1 h-100"
      style="text-align: left; direction: ltr; overflow: hidden auto;"
    >
      <pre>
        {JSON.stringify(entry, undefined, 1)}
      </pre>
    </div>
  </div>
  <div class="tab-pane" class:active={tab_option === "view"}>
    <div
      class="px-1 pb-1 h-100"
      style="text-align: left; direction: ltr; overflow: hidden auto;"
    >
      <Prism code={entry} />
    </div>
  </div>
  <div class="tab-pane" class:active={tab_option === "edit_meta"}>
    <div
      class="px-1 pb-1 h-100"
      style="text-align: left; direction: ltr; overflow: hidden auto;"
    >
      <JSONEditor
        mode={Mode.text}
        bind:content={contentMeta}
        onRenderMenu={handleRenderMenu}
      />
      {#if errorContent}
        <h3 class="mt-3">Error:</h3>
        <Prism bind:code={errorContent} />
      {/if}
    </div>
  </div>
  {#if entry.payload}
    <div class="tab-pane" class:active={tab_option === "edit_content"}>
      <div
        class="px-1 pb-1 h-100"
        style="text-align: left; direction: ltr; overflow: hidden auto;"
      >
        <SchemaEditor bind:content bind:items />
        {#if errorContent}
          <h3 class="mt-3">Error:</h3>
          <Prism bind:code={errorContent} />
        {/if}
      </div>
    </div>
  {/if}

  <div class="tab-pane" class:active={tab_option === "history"}>
    {#key tab_option}
      <ListView
        {space_name}
        {subpath}
        type={QueryType.history}
        shortname={entry.shortname}
        is_clickable={false}
        columns={history_cols}
      />
    {/key}
    <!--History subpath="{entry.subpath}" shortname="{entry.shortname}" /-->
  </div>
  <div class="tab-pane" class:active={tab_option === "attachments"}>
    <Attachments
      {space_name}
      {subpath}
      parent_shortname={entry.shortname}
      attachments={Object.values(entry.attachments)}
    />
  </div>
</div>
