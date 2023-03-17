<script>
  import { Tabs, Tab, TabList, TabPanel } from "svelte-tabs";
  import { status_line } from "./../stores/status_line.js";
  import VirtualList from "svelte-tiny-virtual-list";
  import InfiniteLoading from "svelte-infinite-loading";
  import { dmartCreateContent, dmartGetSchemas, dmartRequest } from "../dmart";
  import { onDestroy } from "svelte";
  import { dmartEntry, dmartQuery } from "../dmart";
  import ContentJsonEditor from "./ContentJsonEditor.svelte";
  import { toastPushSuccess, toastPushFail } from "../utils";
  import AttachmentsManagment from "./AttachmentsManagment.svelte";
  import "bootstrap";
  import Fa from "sveltejs-fontawesome";
  import {
    faCaretSquareLeft,
    faPlusSquare,
    faTrashCan,
  } from "@fortawesome/free-regular-svg-icons";
  import {
    Button,
    Modal,
    ModalBody,
    ModalFooter,
    ModalHeader,
  } from "sveltestrap";
  import { Form, FormGroup, Label, Input } from "sveltestrap";
  import { createAjvValidator, Mode } from "svelte-jsoneditor";
  import { json } from "svelte-i18n";

  let showContentEditSection = false;
  let shortname = "";
  let metaContent = {
    json: {},
    text: undefined,
  };
  let metaContentAttachement = {};
  let bodyContent = {
    json: {},
    text: undefined,
  };

  let historyQuery;
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
      width: "50%",
    },
  };

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
  export let clickable = false;
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

  function cleanUpSchema(obj) {
    for (let prop in obj) {
      if (prop === "comment") delete obj[prop];
      else if (typeof obj[prop] === "object") cleanUpSchema(obj[prop]);
    }
  }

  function handleChange(updatedContent, previousContent, patchResult) {
    const v = patchResult.contentErrors.validationErrors;
    if (v === undefined || v.length === 0) {
      isSchemaValidated = true;
    } else {
      isSchemaValidated = false;
    }
  }

  // TODO TBRemoved
  async function fetchSearchKeys() {
    if (records.length === 0) {
      search.options = [];
    }

    await dmartGetSchemas(query.space_name, schema_shortname)
      .then((json) => {
        const schema = json.records[0].attributes["payload"].body;
        search.options = Object.keys(schema["properties"]);
        cleanUpSchema(schema.properties);
        validator = createAjvValidator({ schema });
        contentSchema = {
          json: schema,
          text: undefined,
        };
      })
      .catch((e) => {
        console.log(e);
      });
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
                items = [...items, ...records];
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

  let delay;
  function handleSearchInput(event) {
    clearTimeout(delay);
    delay = setTimeout(async () => {
      const target = event.target.value;
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
              search:
                search.selected === ""
                  ? `${target}*`
                  : `@${search.selected}:${target}*`,
              limit: 50,
              offset: 50,
            };
      // await fetchRecords(q);
      refreshList();
    }, 500);
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
      const response = await dmartCreateContent(
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

  async function handleDelete() {
    const { resource_type, branch_name, subpath, shortname } = {
      ...records[currentItem - 1],
    };
    const request = {
      space_name: query.space_name,
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
</script>

<svelte:window bind:innerHeight={height} />

<Modal isOpen={open} {toggle} size={"lg"}>
  <ModalHeader />
  <Form on:submit={async (e) => await handleCreateContentSubmit(e)}>
    <ModalBody>
      <FormGroup>
        <Label>Shorname</Label>
        <Input placeholder="Shortname..." bind:value={contentShortname} />
        <hr />

        <Label>Content</Label>
        <ContentJsonEditor
          bind:content
          {validator}
          bind:isSchemaValidated
          handleSave={null}
          onChange={handleChange}
        />

        <hr />

        <Label>Schema</Label>
        <ContentJsonEditor
          bind:self={refJsonEditor}
          content={contentSchema}
          readOnly={true}
          mode={Mode.tree}
        />
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

{#if !showContentEditSection}
  {#if filterable}
    <div class="input-group mb-3">
      <!-- <button
        class="btn btn-outline-secondary dropdown-toggle"
        type="button"
        data-bs-toggle="dropdown"
        aria-expanded="false">Filter</button
      > -->
      <!-- <ul class="dropdown-menu">
        <li>
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
            <p
              class="dropdown-item"
              style="cursor: pointer;"
              on:click={() => handleSearchSelection(option)}
            >
              {option}
            </p>
          </li>
        {/each}
      </ul> -->
      <input
        on:input={handleSearchInput}
        placeholder="{search.selected}..."
        type="text"
        class="form-control"
        aria-label="Text input with dropdown button"
      />
      <!-- svelte-ignore a11y-click-events-have-key-events -->
      <div on:click={async () => await handleCreateContent()}>
        <Fa icon={faPlusSquare} size={"3x"} color={"grey"} />
      </div>
    </div>
  {/if}

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
          if (!clickable || index === 0) {
            return;
          }

          currentItem = index;
          showContentEditSection = true;
          const record = { ...records[index - 1] };

          shortname = record.shortname;
          const json = { ...record };
          metaContentAttachement = json.attachments;
          console.log({ metaContentAttachement });

          delete json.attachments;
          metaContent = {
            json,
            text: undefined,
          };

          if (record?.attributes?.payload?.body) {
            bodyContent = {
              json: await dmartEntry(
                record.resource_type,
                query.space_name,
                record.subpath,
                shortname,
                schema_shortname,
                "json"
              ),
              text: undefined,
            };
          }

          historyQuery = {
            type: "history",
            space_name: query.space_name,
            filter_shortnames: [shortname],
            subpath: record.subpath,
            retrieve_json_payload: true,
          };
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
            <div class="my-cell" style=" width: {cols[col].width};">
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
  <div class="d-flex justify-content-between">
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div
      class="back-icon"
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
      <AttachmentsManagment
        bind:attachments={metaContentAttachement}
        bind:space_name={query.space_name}
        bind:subpath={query.subpath}
        bind:entryShortname={records[currentItem - 1].shortname}
      />
    </TabPanel>

    <TabPanel>
      <div style="height: {height}">
        <svelte:self
          bind:query={historyQuery}
          bind:cols={historyCols}
          details_split={0}
        />
      </div>
    </TabPanel>
  </Tabs>
{/if}

<style>
  .back-icon {
    margin-top: 8px;
    margin-left: 8px;
  }
  h5 {
    margin-top: 8px;
    margin-left: 8px;
  }
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
