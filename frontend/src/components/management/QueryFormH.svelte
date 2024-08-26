<script lang="ts">
  import { _ } from "@/i18n";
  import {
    type AggregationType,
    type QueryRequest,
    QueryType,
    ResourceType,
    csv,
    get_children,
    get_spaces,
    query,
  } from "@/dmart";
  import { createEventDispatcher, onMount } from "svelte";
  import { Button, Col, Row, Form, Icon } from "sveltestrap";
  import downloadFile from "@/utils/downloadFile";
  import { Level, showToast } from "@/utils/toast";
  import Input from "../Input.svelte";
  import Aggregation from "./Aggregation.svelte";

  const dispatch = createEventDispatcher();
  let spaces = [];

  onMount(() => {
    async function setup() {
      spaces = (await get_spaces()).records;
    }
    setup();
  });

  let aggregation_data = {
    load: [],
    group_by: [],
    reducers: [],
  };
  let formData = null;
  async function handleResponse(event) {
    event.preventDefault();

    const fd = new FormData(event.target);
    let record: any = {};
    for (var pair of fd.entries()) {
      record[pair[0]] = pair[1];
    }
    formData = record;
    const {
      type,
      space_name,
      subpath,
      resource_type,
      resource_shortnames,
      search,
      from_date,
      to_date,
      offset,
      limit,
      retrieve_attachments,
      retrieve_json_payload,
    } = record;

    if (!spacename || !subpath || !queryType){
        formData = null;
        return;
    }

    const query_request: QueryRequest = {
      type,
      space_name,
      subpath,
      filter_types: resource_type ? [resource_type] : [],
      filter_shortnames: resource_shortnames
        ? resource_shortnames.split(",")
        : [],
      retrieve_attachments,
      retrieve_json_payload,
      exact_subpath: true,
      search: search || "",
      offset,
      limit,
    };
    if (from_date) {
      query_request.from_date = `${from_date}T00:00:00.000Z`;
    }
    if (to_date) {
      query_request.from_date = `${to_date}T00:00:00.000Z`;
    }
    if (query_request.type === QueryType.aggregation) {
      // query_request.
      const aggregations: any = aggregation_data.reducers.map((agg) => {
        return { ...agg, args: agg.args.split(",") };
      });
      query_request.aggregation_data = aggregations;
    }
    const response = await query(query_request);
    dispatch("response", response);
  }

  let spacename = "management";
  let queryType = "";
  let selectedSpacename = "";
  let subpath = "/";
  let tempSubpaths = [];
  let subpaths = [{ records: [{ shortname: "/", resource_type: "folder" }] }];

  async function buildSubpaths(base, _subpaths) {
    await Promise.all(
      await _subpaths.records.map(async (_subpath) => {
        if (_subpath.resource_type === "folder") {
          const _subpaths = await get_children(spacename, _subpath.shortname);
          await buildSubpaths(`${base}/${_subpath.shortname}`, _subpaths);
          tempSubpaths.push(`${base}/${_subpath.shortname}`);
        }
      })
    );
  }
  $: spacename,
    (() => {
      if (selectedSpacename !== spacename) {
        (async () => {
          subpaths = [];
          tempSubpaths = [];
          const _subpaths = await get_children(spacename, "/");
          await buildSubpaths("", _subpaths);

          subpaths = [...tempSubpaths.reverse()];
          selectedSpacename = `${spacename}`;
        })();
      }
    })();
  let isDisplayFilter = false;
  async function handleDownload() {
    const {
      space_name,
      subpath,
      resource_type,
      resource_shortnames,
      search,
      from_date,
      to_date,
      offset,
      limit,
    } = formData;
    const body: any = {
      space_name,
      subpath,
      type: "search",
      search: search || "",
      retrieve_json_payload: true,
      filter_types: resource_type ? [resource_type] : [],
      filter_shortnames: resource_shortnames
        ? resource_shortnames.split(",")
        : [],
      offset,
      limit,
    };
    if (from_date) {
      body.from_date = `${from_date}T00:00:00.000Z`;
    }
    if (to_date) {
      body.from_date = `${to_date}T00:00:00.000Z`;
    }
    const data = await csv(body);
    if (data?.status === "failed") {
      showToast(Level.warn);
    } else {
      downloadFile(data, `${space_name}/${subpath}.csv`, "text/csv");
    }
  }
</script>

<Form on:submit={handleResponse}>
  <Row>
    <Col sm="4">
      <Row>
        <Col class="d-flex align-items-center" sm="1">
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
          <h4
            class="my-4"
            style="cursor: pointer;"
            on:click={() => (isDisplayFilter = !isDisplayFilter)}
          >
            <Icon
              name={isDisplayFilter ? "filter-circle-fill" : "filter-circle"}
              size={32}
            />
          </h4>
        </Col>
        <Col sm="11">
          <Input
            id="type"
            type="select"
            title={$_("query_type")}
            bind:value={queryType}
            required
          >
            {#each Object.keys(QueryType) as queryType}
              <option value={queryType}>{queryType}</option>
            {/each}
          </Input>
        </Col>
      </Row>
    </Col>
    <Col sm="4">
      <Input
        id="space_name"
        type="select"
        title={$_("space_name")}
        bind:value={spacename}
      >
        {#each spaces as space}
          <option value={space.shortname}>{space.shortname}</option>
        {/each}
      </Input></Col
    >
    <Col sm="4">
      <Input
        id="subpath"
        type="select"
        title={$_("subpath")}
        bind:value={subpath}
      >
        <option value={"/"}>/</option>
        {#each subpaths as subpath}
          <option value={subpath}>{subpath}</option>
        {/each}
      </Input></Col
    >
  </Row>
  {#if isDisplayFilter}
    <Row>
      <Col sm="4">
        <Input id="resource_type" type="select" title={$_("resource_types")}>
          {#each Object.keys(ResourceType) as resourceType}
            <option value={resourceType}>{resourceType}</option>
          {/each}
        </Input>
      </Col>
      <Col sm="4">
        <Input id="search" type="text" title={$_("search")} value="" />
      </Col>
      <Col sm="4">
        <Input id="resource_shortnames" type="text" title={$_("shortnames")} />
      </Col>
    </Row>
    <Row>
      <Col sm="4">
        <Input id="from_date" type="date" title={$_("from")} value={""} /></Col
      >
      <Col sm="4">
        <Input id="to_date" type="date" title={$_("to")} value={""} /></Col
      >
      <Col class="d-flex align-items-end" sm="4">
        <Input
          id="retrieve_attachments"
          type="checkbox"
          title={$_("retrieve_attachments")}
          value={true}
        /></Col
      >
    </Row>
    <Row>
      <Col sm="4">
        <Input id="limit" type="number" title={$_("limit")} value={"10"} /></Col
      >
      <Col sm="4">
        <Input
          id="offset"
          type="number"
          title={$_("offset")}
          value={"0"}
        /></Col
      >
      <Col class="d-flex align-items-end" sm="4">
        <Input
          id="retrieve_json_payload"
          type="checkbox"
          title={$_("retrieve_json_payload")}
          value={true}
        /></Col
      >
    </Row>
  {/if}
  {#if queryType === QueryType.aggregation}
    <Aggregation bind:aggregation_data />
  {/if}

  <Row>
    <Col class="d-flex justify-content-between mb-2">
      <Button outline type="submit">{$_("submit")}</Button>
      {#if formData}
        <Button outline type="button" on:click={handleDownload}
          >{$_("download_csv")}</Button
        >
      {/if}
    </Col>
  </Row>
</Form>
