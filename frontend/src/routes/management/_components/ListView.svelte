<script>
  import { status_line } from "../_stores/status_line.js";
  import VirtualList from "svelte-tiny-virtual-list";
  import InfiniteLoading from "svelte-infinite-loading";
  import {
    dmartManContent,
    dmartGetSchemas,
    dmartRequest,
  } from "../../../dmart.js";
  import { onDestroy } from "svelte";
  import { dmartEntry, dmartQuery } from "../../../dmart.js";
  import {
    toastPushSuccess,
    toastPushFail,
    toastPushLoding,
    toastPop,
  } from "../../../utils.js";
  import { Breadcrumb, BreadcrumbItem } from "sveltestrap";
  import { createAjvValidator, Mode } from "svelte-jsoneditor";
  import ContentEditSection from "./ContentEditSection.svelte";
  import {
    triggerRefreshList,
    triggerSearchList,
  } from "../_stores/trigger_refresh.js";
  import { goto } from "@roxi/routify";

  let showContentEditSection = false;
  let shortname = "";
  let metaContent = {
    json: {},
    text: undefined,
  };
  let errorContent = {
    json: {},
    text: undefined,
  };
  let isError = false;
  let metaContentAttachement = {};
  let bodyContent = {
    json: {},
    text: undefined,
  };

  let historyQuery;

  let content = {
    json: {},
    text: undefined,
  };
  let contentSchema = {
    json: {},
    text: undefined,
  };
  let isSchemaValidated = false;
  let validator = createAjvValidator({ schema: {} });

  onDestroy(() => status_line.set(""));
  export let query;

  const base_query = { ...query };
  export let cols;
  export let details_split = 0;
  export let filterable = false;

  let total;
  let lastbatch;
  let page = 0;
  let items = [{}];
  let currentItem = {};
  let api_status = "-";
  let records = [];
  let schema_shortname = "";
  let search = {
    selected: "",
    options: [],
  };
  let infiniteId = Symbol();

  function handleChange(updatedContent, previousContent, patchResult) {
    const v = patchResult.contentErrors.validationErrors;
    if (v === undefined || v.length === 0) {
      isSchemaValidated = true;
    } else {
      isSchemaValidated = false;
    }
  }

  async function infiniteHandler({ detail: { loaded, complete, error } }) {
    if (Object.keys(query).length <= 2) {
      complete();
    } else {
      try {
        query.limit = 50;
        query.offset = 50 * page;
        await dmartQuery(query)
          .then(async (json) => {
            records = [...records, ...json.records];
            if (json.status == "success") {
              lastbatch = json.attributes.returned;
              total = json.attributes.total;
              if (schema_shortname === "") {
                schema_shortname =
                  records[0]?.attributes?.payload?.schema_shortname;
              }
              if (lastbatch) {
                page += 1;
                items = [...items, ...json.records];
                loaded();
              } else {
                complete();
              }
              api_status = "success";
              status_line.set(
                `Loaded ${items.length - 1} of ${total}.<br/>api: ${api_status}`
              );
            } else {
              console.log("Error with query", json);
              api_status = json || "Unknown error";
              status_line.set(`api: ${api_status}`);
            }
          })
          .catch((e) => {
            console.log(e);
          });
        // if (filterable && search.options.length === 0) {
        //   await fetchSearchKeys();
        // }
      } catch (e) {
        console.log(e);
      }
    }
  }

  function value(path, data, type) {
    if (path.length == 1 && path[0].length > 0 && path[0] in data) {
      if (type == "json") return JSON.stringify(data[path[0]], undefined, 1);
      else return data[path[0]];
    }

    if (path.length > 1 && path[0].length > 0 && path[0] in data) {
      return value(path.slice(1), data[path[0]], type);
    }

    return "not_applicable";
  }

  const handleSave = async () => {
    if (!isSchemaValidated) {
      alert("The content does is not validated agains the schema");
      return;
    }
    isError = false;

    const metaData = metaContent.json
      ? { ...metaContent.json }
      : JSON.parse(metaContent.text);
    const data = { ...metaData };
    data.attributes.payload.body =
      bodyContent.json ??
      JSON.parse(bodyContent.text) ??
      data.attributes.payload.body;
    const response = await dmartRequest("managed/request", {
      space_name: query.space_name,
      request_type: "update",
      records: [data],
    });
    if (response.status === "success") {
      toastPushSuccess();
      records[currentItem - 1] = metaData;
    } else {
      toastPushFail();
      errorContent.json = response.error;
      isError = true;
    }
  };

  function handleSearchSelection(option) {
    search.selected = option;
  }

  function refreshList() {
    currentItem = {};
    page = 0;
    records = [];
    items = [{}];
    infiniteId = Symbol();
  }

  function handleSearchInput(target) {
    query =
      target === ""
        ? base_query
        : {
            request_type: "query",
            space_name: query.space_name,
            type: "search",
            subpath: query.subpath,
            retrieve_json_payload: true,
            filter_schema_names: [
              search.selected === "" ? "meta" : schema_shortname,
            ],
            search: target ? `${target}` : "",
            // search:
            //   search.selected === ""
            //     ? `${target}*`
            //     : `@${search.selected}:${target}*`,
            limit: 50,
            offset: 50,
          };
    // await fetchRecords(q);
    refreshList();
  }

  let height;

  async function handleCreateContent() {
    open = true;
  }
  let open = false;
  let contentShortname = "";
  async function handleCreateContentSubmit(e) {
    e.preventDefault();

    if (isSchemaValidated) {
      const response = await dmartManContent(
        base_query.space_name,
        base_query.subpath,
        contentShortname === "" ? "auto" : contentShortname,
        schema_shortname,
        JSON.parse(content.text)
      );
      if (response.status === "success") {
        toastPushSuccess();
        refreshList();
        open = false;
      } else {
        toastPushFail();
      }
    }
  }
  function toggle() {
    open != open;
  }

  let refJsonEditor;

  $: {
    refJsonEditor?.expand(() => false);
  }
  $: {
    if ($triggerRefreshList) {
      refreshList();
    }
  }
  $: triggerSearchList && handleSearchInput($triggerSearchList);
  $: {
    if (!showContentEditSection) {
      shortname = "";
    }
  }
</script>

<svelte:window bind:innerHeight={height} />

{#if filterable}
  <div class="input-group">
    <Breadcrumb class="mt-3 px-3">
      <BreadcrumbItem>{query.space_name}</BreadcrumbItem>
      {#each query.subpath.split("/") as s}
        {#if s !== ""}
          <BreadcrumbItem>{s}</BreadcrumbItem>
        {/if}
      {/each}
      {#if shortname}
        <BreadcrumbItem>{shortname}</BreadcrumbItem>
      {/if}
    </Breadcrumb>
  </div>
{/if}
{#if !showContentEditSection}
  <div class="list">
    <VirtualList
      height={height - 105}
      width="auto"
      stickyIndices={[0]}
      itemCount={items.length}
      overscanCount={100}
      itemSize={25}
    >
      <!-- svelte-ignore a11y-click-events-have-key-events -->
      <div
        slot="item"
        let:index
        let:style
        style={style.replaceAll("left:0;", "")}
        class="my-row"
        on:click={async () => {
          const record = { ...records[index - 1] };
          shortname = record.shortname;
          schema_shortname = record.attributes?.payload?.schema_shortname;
          window.history.replaceState(
            history.state,
            "",
            `/management/dashboard/${
              query.space_name
            }/${record.subpath.replaceAll("/", "-")}/${shortname}/${
              record.resource_type
            }/${schema_shortname}`
          );
        }}
        class:current={currentItem == index}
      >
        {#if index == 0}
          {#each Object.keys(cols) as col}
            <div class="my-cell" style="width: {cols[col].width};">
              <strong>{cols[col].title}</strong>
            </div>
          {/each}
        {:else}
          {#each Object.keys(cols) as col}
            <div
              class="my-cell hide-scroll"
              style=" width: {cols[col].width};overflow: auto;"
            >
              {value(cols[col].path.split("."), items[index], cols[col].type)}
            </div>
          {/each}
        {/if}
      </div>
      <div slot="footer">
        <InfiniteLoading on:infinite={infiniteHandler} identifier={infiniteId}>
          <span slot="noResults" />
          <span slot="noMore" />
          <span slot="error" />
        </InfiniteLoading>
      </div>
    </VirtualList>

    {#if currentItem && currentItem > 0 && details_split > 0}
      <div
        class="one-item pt-2"
        style="height: {details_split}px; overflow: hide;"
      >
        {#each Object.keys(items[currentItem]) as key}
          <span class="w-50" style="text-align: right;"
            ><strong>{key}: </strong></span
          >
          <span class="w-50">
            <code>{JSON.stringify(items[currentItem][key]).trim()}</code>
          </span>
        {/each}
      </div>
    {/if}
  </div>
{/if}

{#if showContentEditSection}
  <ContentEditSection
    bind:space_name={query.space_name}
    bind:subpath={query.subpath}
    bind:records
    bind:bodyContent
    bind:metaContent
    bind:errorContent
    bind:validator
    bind:isSchemaValidated
    bind:isError
    bind:metaContentAttachement
    bind:historyQuery
    bind:showContentEditSection
    {handleSave}
    bind:currentItem
    bind:shortname
    bind:height
  />
{/if}

<style>
  /*
  .back-icon {
    margin-top: 8px;
    margin-left: 8px;
  }
  h5 {
    margin-top: 8px;
    margin-left: 8px;
  }*/
  /* hr {
    color: green;
    background-color: blue;
    height: 5px;
    user-select: none;
    margin: 0;
    position: absolute;
    border: solid 1px gray;
  } 
  */
  :global(.virtual-list-wrapper) {
    margin: 0 0px;
    background: #fff;
    border-radius: 2px;
    box-shadow: 0 2px 2px 0 rgba(0, 0, 0, 0.14),
      0 3px 1px -2px rgba(0, 0, 0, 0.2), 0 1px 5px 0 rgba(0, 0, 0, 0.12);
    background: #fafafa;
    font-family: -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif;
    color: #333;
    -webkit-font-smoothing: antialiased;
  }

  .my-row {
    padding: 0 15px;
    border-bottom: 1px solid #eee;
    box-sizing: border-box;
    height: 30px;
    font-weight: 500;
    background: #fff;
    display: flex;
    justify-content: space-between;
    cursor: pointer;
  }

  .my-row:hover {
    background-color: #ddd;
  }

  .current {
    background-color: yellowgreen;
  }

  .my-cell {
    display: inline;
    /*border: 1px solid orange;*/
  }

  /* Hide scrollbar for Chrome, Safari and Opera */
  .hide-scroll::-webkit-scrollbar {
    display: none;
  }

  /* Hide scrollbar for IE, Edge and Firefox */
  .hide-scroll {
    -ms-overflow-style: none; /* IE and Edge */
    scrollbar-width: none; /* Firefox */
  }
</style>
