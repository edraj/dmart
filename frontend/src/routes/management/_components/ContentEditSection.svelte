<script>
  import { Tabs, Tab, TabList, TabPanel } from "svelte-tabs";
  import Fa from "sveltejs-fontawesome";
  import {
    faCaretSquareLeft,
    faTrashCan,
  } from "@fortawesome/free-regular-svg-icons";
  import ContentJsonEditor from "./ContentJsonEditor.svelte";
  import { toastPushSuccess, toastPushFail } from "../../../utils.js";
  import AttachmentsManagment from "./AttachmentsManagment.svelte";
  import ListView from "./ListView.svelte";

  export let space_name, subpath;
  export let records;
  export let bodyContent;
  export let metaContent;
  export let errorContent;
  export let isError;
  export let metaContentAttachement;
  export let historyQuery;
  export let showContentEditSection;
  export let handleSave;
  export let currentItem;
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

  async function handleDelete() {
    if (confirm(`Are you sure want to delete ${shortname} entry`) === false) {
      return;
    }

    const { resource_type, branch_name, subpath, shortname } = {
      ...records[currentItem - 1],
    };
    const request = {
      space_name,
      request_type: "delete",
      records: [
        {
          resource_type,
          shortname,
          subpath,
          branch_name,
          attributes: {},
        },
      ],
    };
    const response = await dmartRequest("managed/request", request);
    if (response.status === "success") {
      toastPushSuccess();
      refreshList();
      showContentEditSection = false;
    } else {
      toastPushFail();
    }
  }

  async function updateSingleEntry() {
    const { subpath, branch_name, shortname } = records[currentItem - 1];
    const request = {
      type: "subpath",
      space_name: space_name,
      subpath,
      branch_name,
      filter_schema_names: ["meta"],
      filter_shortnames: [shortname],
      retrieve_json_payload: true,
      retrieve_attachments: true,
    };
    const response = await dmartRequest("managed/query", request);
    if (response.status === "success") {
      toastPushSuccess();
      records[currentItem - 1] = response.records[0];
      metaContentAttachement = records[currentItem - 1].attachments;
    } else {
      toastPushFail();
    }
  }
</script>

<div class="d-flex justify-content-between">
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <div
    class="back-icon"
    style="cursor: pointer;"
    on:click={() => {
      showContentEditSection = false;
    }}
  >
    <Fa icon={faCaretSquareLeft} size="lg" color="dimgrey" />
  </div>
  <h5 class="mx-2">{shortname}</h5>
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <div
    class="back-icon"
    style="cursor: pointer;"
    on:click={async () => {
      await handleDelete();
    }}
  >
    <Fa icon={faTrashCan} size="lg" color="dimgrey" />
  </div>
</div>
<hr />
<Tabs>
  <TabList>
    <Tab>Content</Tab>
    <Tab>Meta</Tab>
    <Tab>Attachments</Tab>
    <Tab>History</Tab>
  </TabList>

  <TabPanel>
    <ContentJsonEditor bind:content={bodyContent} {handleSave} />
  </TabPanel>
  <TabPanel>
    <ContentJsonEditor bind:content={metaContent} {handleSave} />
  </TabPanel>
  <TabPanel>
    {#key records}
      <AttachmentsManagment
        bind:attachments={metaContentAttachement}
        bind:space_name
        bind:subpath
        bind:entryShortname={records[currentItem - 1].shortname}
        forceRefresh={async () => await updateSingleEntry()}
      />
    {/key}
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
