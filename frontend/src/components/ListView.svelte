<script>
  import { Tabs, Tab, TabList, TabPanel } from "svelte-tabs";
  import { status_line } from "./../stores/status_line.js";
  import VirtualList from "svelte-tiny-virtual-list";
  import InfiniteLoading from "svelte-infinite-loading";
  import { dmart_request } from "../dmart";
  import { onDestroy } from "svelte";
  import { dmart_entry, dmart_query } from "../dmart";
  import ContentJsonEditor from "./ContentJsonEditor.svelte";
  import { toastPushSuccess, toastPushFail } from "../utils";
  import AttachmentsManagment from "./AttachmentsManagment.svelte";
  import "bootstrap";

  let showModal = false;

  let metaContent = {
    json: null,
    text: undefined,
  };

  let bodyContent = {
    json: null,
    text: undefined,
  };

  let history_query;
  let history_cols = {
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
      width: "50%",
    },
  };

  onDestroy(() => status_line.set(""));
  export let query;
  export let cols;
  export let details_split = 0;
  export let clickable = false;
  export let filterable = false;

  let total;
  let lastbatch;
  let page = 0;
  let items = [{}];
  let current_item = {};
  let api_status = "-";
  let records = [];
  let schema_shortname = "";
  let search = {
    selected: "",
    options: [],
  };
  let infiniteId = Symbol();

  async function fetchSearchKeys() {
    if (records.length === 0) {
      search.options = [];
    }
    await dmart_query({
      type: "subpath",
      filter_types: ["schema"],
      space_name: query.space_name,
      subpath: "schema",
      retrieve_json_payload: true,
      filter_shortnames: [schema_shortname],
      limit: 100,
      offset: 0,
    })
      .then((json) => {
        search.options = Object.keys(
          json.records[0].attributes["payload"].body["properties"]
        );
      })
      .catch((e) => {
        console.log(e);
        error();
      });
  }

  async function infiniteHandler({ detail: { loaded, complete, error } }) {
    if (Object.keys(query).length <= 2) {
      complete();
      return;
    }
    try {
      query.limit = 50;
      query.offset = 50 * page;
      await dmart_query(query)
        .then(async (json) => {
          records = [...records, ...json.records.reverse()];
          if (json.status == "success") {
            lastbatch = json.attributes.returned;
            total = json.attributes.total;
            if (schema_shortname === "") {
              schema_shortname =
                records[0]?.attributes?.payload?.schema_shortname;
            }
            if (lastbatch) {
              page += 1;
              items = [...items, ...records];
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
          error();
        });
      if (filterable && search.options.length === 0) {
        await fetchSearchKeys();
      }
    } catch (e) {
      console.log(e);
      error();
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
  let listHeight;
  let resizing = false;
  function resize(e) {
    if (resizing) {
      details_split =
        details_split - e.movementY > 0 ? details_split - e.movementY : 0;
    }
  }

  const handleSave = async () => {
    delete metaContent.json.attachments;
    const data = metaContent.json;
    data.attributes.payload.body =
      bodyContent.json ?? metaContent.json.attributes.payload.body;
    const response = await dmart_request("managed/request", {
      space_name: query.space_name,
      request_type: "update",
      records: [data],
    });
    if (response.status === "success") {
      toastPushSuccess();
    } else {
      toastPushFail();
    }
  };

  function handleSearchSelection(option) {
    search.selected = option;
  }
  let delay;
  function handleSearchInput(event) {
    clearTimeout(delay);
    delay = setTimeout(async () => {
      const target = event.target.value;
      records = [];
      items = [{}];
      page = 0;
      // if (target === "") {
      //   // await fetchRecords(query);
      // }
      query = {
        request_type: "query",
        space_name: query.space_name,
        type: "search",
        subpath: query.subpath,
        retrieve_json_payload: true,
        filter_schema_names: [schema_shortname],
        search:
          search.selected === ""
            ? `${target}*`
            : `@${search.selected}:${target}*`,
        limit: 50,
        offset: 50,
      };
      // await fetchRecords(q);
      infiniteId = Symbol();
    }, 500);
  }
</script>

<svelte:window on:mouseup={() => (resizing = false)} on:mousemove={resize} />

{#if !showModal}
  {#if filterable}
    <div class="input-group mb-3">
      <button
        class="btn btn-outline-secondary dropdown-toggle"
        type="button"
        data-bs-toggle="dropdown"
        aria-expanded="false">Filter</button
      >
      <ul class="dropdown-menu">
        <li>
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <p
            class="dropdown-item"
            style="cursor: pointer;"
            on:click={() => handleSearchSelection("")}
          >
            Anything
          </p>
        </li>
        {#each search.options as option (option)}
          <li>
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <p
              class="dropdown-item"
              style="cursor: pointer;"
              on:click={() => handleSearchSelection(option)}
            >
              {option}
            </p>
          </li>
        {/each}
      </ul>
      <input
        on:input={handleSearchInput}
        placeholder="{search.selected}..."
        type="text"
        class="form-control"
        aria-label="Text input with dropdown button"
      />
    </div>
  {/if}
  <div class="list h-100" bind:offsetHeight={listHeight}>
    <VirtualList
      height={listHeight - details_split - 5}
      width="auto"
      stickyIndices={[0]}
      itemCount={items.length}
      overscanCount={100}
      itemSize={25}
    >
      <!--div slot="header" style="padding: 0 15px;"> 
    </div-->
      <!-- svelte-ignore a11y-click-events-have-key-events -->
      <div
        slot="item"
        let:index
        let:style
        style={style.replaceAll("left:0;", "")}
        class="my-row"
        on:click={async () => {
          if (!clickable) {
            return;
          }

          current_item = index;
          showModal = true;

          if (records[index - 1]?.attributes?.payload?.body) {
            bodyContent = {
              json: await dmart_entry(
                records[index - 1].resource_type,
                query.space_name,
                records[index - 1].subpath,
                records[index - 1].shortname,
                schema_shortname,
                "json"
              ),
              text: undefined,
            };
          }

          metaContent = {
            json: records[index - 1],
            text: undefined,
          };

          history_query = {
            type: "history",
            space_name: query.space_name,
            filter_shortnames: [records[index - 1].shortname],
            subpath: records[index - 1].subpath,
            retrieve_json_payload: true,
          };
        }}
        class:current={current_item == index}
      >
        {#if index == 0}
          <div class="my-cell" style="width: 5%;">#</div>
          {#each Object.keys(cols) as col}
            <div class="my-cell" style="width: {cols[col].width};">
              <strong>{cols[col].title}</strong>
            </div>
          {/each}
        {:else}
          <div class="my-cell" style="width: 5%;" />
          {#each Object.keys(cols) as col}
            <div class="my-cell" style=" width: {cols[col].width};">
              {value(cols[col].path.split("."), items[index], cols[col].type)}
            </div>
          {/each}
        {/if}
      </div>
      <div slot="footer">
        <InfiniteLoading
          on:infinite={infiniteHandler}
          identifier={infiniteId}
        />
      </div>
    </VirtualList>
    <hr
      on:mousedown={() => (resizing = true)}
      style="cursor: {resizing ? 'grabbing' : 'grab'}"
    />
    {#if current_item && current_item > 0 && details_split > 0}
      <div
        class="one-item pt-2"
        style="height: {details_split}px; overflow: hide;"
      >
        {#each Object.keys(items[current_item]) as key}
          <span class="w-50" style="text-align: right;"
            ><strong>{key}: </strong></span
          >
          <span class="w-50">
            <code>{JSON.stringify(items[current_item][key]).trim()}</code>
          </span>
        {/each}
      </div>
    {/if}
  </div>
{/if}

{#if showModal}
  <Tabs>
    <TabList>
      <Tab>Content</Tab>
      <Tab>Attachments</Tab>
      <Tab>History</Tab>
    </TabList>

    <TabPanel>
      <ContentJsonEditor bind:content={metaContent} {handleSave} />
      <ContentJsonEditor bind:content={bodyContent} {handleSave} />
    </TabPanel>

    <TabPanel>
      <AttachmentsManagment
        bind:content={metaContent.json.attachments}
        bind:space_name={query.space_name}
      />
    </TabPanel>

    <TabPanel>
      <div style="height: 100vh">
        <svelte:self
          bind:query={history_query}
          bind:cols={history_cols}
          details_split={0}
        />
      </div>
    </TabPanel>
  </Tabs>
{/if}

<style>
  hr {
    color: green;
    background-color: blue;
    height: 5px;
    user-select: none;
    margin: 0;
    /*position: absolute;*/
    /*border: solid 1px gray;*/
  }
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
    line-height: 25px;
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
</style>
