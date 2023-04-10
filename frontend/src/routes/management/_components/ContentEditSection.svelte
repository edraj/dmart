<script>
  import { Tabs, TabList, TabPanel, Tab } from "./tabs/tabs";
  import Fa from "sveltejs-fontawesome";
  import {
    faCaretSquareLeft,
    faTrashCan,
  } from "@fortawesome/free-regular-svg-icons";
  import ContentJsonEditor from "./ContentJsonEditor.svelte";
  import { toastPushSuccess, toastPushFail } from "../../../utils.js";
  import AttachmentsManagment from "./AttachmentsManagment.svelte";
  import ListView from "./ListView.svelte";
  import { dmartRequest } from "../../../dmart";
  import { Breadcrumb, BreadcrumbItem } from "sveltestrap";

  export let space_name, subpath, resource_type;
  export let bodyContent;
  export let metaContent;
  export let errorContent;
  export let validator;
  export let isSchemaValidated;
  export let isError;
  export let metaContentAttachement;
  export let historyQuery;
  let showContentEditSection;
  export let handleSave;
  export let shortname;
  export let height;

  let historyCols = {
    owner_shortname: {
      path: "attributes.owner_shortname",
      title: "Owner shorname",
      type: "string",
      width: "15%",
    },
    created_at: {
      path: "attributes.created_at",
      title: "Created At",
      type: "string",
      width: "15%",
    },
    updated_at: {
      path: "attributes.updated_at",
      title: "Updated At",
      type: "string",
      width: "15%",
    },
    diff: {
      path: "attributes.diff",
      title: "Diff",
      type: "json",
      width: "55%",
    },
  };

  function back() {
    window.history.replaceState(
      history.state,
      "",
      `/management/dashboard/${space_name}/${subpath.replaceAll("/", "-")}`
    );
  }

  async function handleDelete() {
    if (confirm(`Are you sure want to delete ${shortname} entry`) === false) {
      return;
    }
    showContentEditSection = false;
    const request = {
      space_name,
      request_type: "delete",
      records: [
        {
          resource_type,
          shortname,
          subpath,
          branch_name: "master",
          attributes: {},
        },
      ],
    };
    const response = await dmartRequest("managed/request", request);
    if (response.status === "success") {
      toastPushSuccess();
      back();
    } else {
      toastPushFail();
    }
  }

  async function updateSingleEntry() {
    const request = {
      type: "subpath",
      space_name: space_name,
      subpath,
      branch_name: "master",
      filter_schema_names: ["meta"],
      filter_shortnames: [shortname],
      retrieve_json_payload: true,
      retrieve_attachments: true,
    };
    const response = await dmartRequest("managed/query", request);
    if (response.status === "success") {
      toastPushSuccess();
    } else {
      toastPushFail();
    }
  }
</script>

<Breadcrumb class="mt-3 px-3">
  <BreadcrumbItem>{space_name}</BreadcrumbItem>
  {#each subpath.split("/") as s}
    {#if s !== ""}
      <BreadcrumbItem>{s}</BreadcrumbItem>
    {/if}
  {/each}
  {#if shortname}
    <BreadcrumbItem>{shortname}</BreadcrumbItem>
  {/if}
</Breadcrumb>

<Tabs>
  <TabList>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div class="tab-list back-icon" style="cursor: pointer;" on:click={back}>
      <Fa icon={faCaretSquareLeft} size="lg" color="dimgrey" />
    </div>
    <div class="tab-list">
      {#if bodyContent.json !== null}
        <Tab>Content</Tab>
      {/if}
      <Tab>Meta</Tab>
      <Tab>Attachments</Tab>
      <Tab>History</Tab>
    </div>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div
      class="tab-list back-icon"
      style="cursor: pointer;"
      on:click={async () => {
        await handleDelete();
      }}
    >
      <Fa icon={faTrashCan} size="lg" color="dimgrey" />
    </div>
  </TabList>

  {#if bodyContent.json !== null}
    <TabPanel>
      <ContentJsonEditor
        bind:content={bodyContent}
        {handleSave}
        {validator}
        bind:isSchemaValidated
      />
    </TabPanel>
  {/if}
  <TabPanel>
    <ContentJsonEditor bind:content={metaContent} {handleSave} />
  </TabPanel>
  <TabPanel>
    <AttachmentsManagment
      bind:attachments={metaContentAttachement}
      bind:space_name
      bind:subpath
      bind:entryShortname={shortname}
      forceRefresh={async () => await updateSingleEntry()}
    />
  </TabPanel>

  <TabPanel>
    <div style="height: {height}">
      <ListView
        bind:query={historyQuery}
        bind:cols={historyCols}
        details_split={0}
      />
    </div>
  </TabPanel>
</Tabs>

{#if isError}
  <div class="mt-3">
    <h3>Error details</h3>
    <ContentJsonEditor bind:content={errorContent} readOnly={true} />
  </div>
{/if}
