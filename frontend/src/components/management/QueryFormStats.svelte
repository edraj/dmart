<script lang="ts">
  import {_} from "@/i18n";
  import {csv, get_children, get_spaces, query, type QueryRequest, QueryType, ResourceType,} from "@/dmart";
  import {createEventDispatcher, onMount} from "svelte";
  import {Button, Col, Form, Icon, Row} from "sveltestrap";
  import Input from "../Input.svelte";
  import Aggregation from "./Aggregation.svelte";

  const dispatch = createEventDispatcher();
  let spaces = $state([]);

  onMount(() => {
    async function setup() {
      spaces = (await get_spaces()).records;
    }
    setup();
  });

  let aggregation_data = $state({
    load: [],
    group_by: [],
    reducers: [],
  });
  let formData = $state(null);
  async function handleResponse(event : any) {
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
      retrieve_json_payload: true,
      retrieve_attachments: false,
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

  let spacename : string = $state(null);
  let queryType : QueryType = $state(null);
  let subpath : string = $state("/");

  let selectedSpacename = null;
  let tempSubpaths = $state([]);
  let subpaths = $state([{ records: [{ shortname: "/", resource_type: "folder" }] }]);

  async function buildSubpaths(base: string, _subpaths: any) {
    for (const _subpath of _subpaths.records) {
      if (_subpath.resource_type === "folder") {
        const childSubpaths = await get_children(spacename, _subpath.shortname);
        await buildSubpaths(`${base}/${_subpath.shortname}`, childSubpaths);
        tempSubpaths.push(`${base}/${_subpath.shortname}`);
      }
    }
  }

  let isDisplayFilter = $state(false);

  $effect(() => {
    if (spacename && selectedSpacename !== spacename) {
      (async () => {
        subpaths = [];
        tempSubpaths = [];
        const _subpaths = await get_children(spacename, "/");

        await buildSubpaths("", _subpaths);

        subpaths = [...tempSubpaths.reverse()];
        selectedSpacename = `${spacename}`;
      })();
    }
  });
</script>

<Form on:submit={handleResponse}>
  <Row>
    <Col sm="4">
      <Row>
        <Col class="d-flex align-items-center" sm="1">
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <div
            style=";cursor: pointer;"
            onclick={() => (isDisplayFilter = !isDisplayFilter)}
          >
            <Icon
              name={isDisplayFilter ? "filter-circle-fill" : "filter-circle"}
              size={32}
            />
          </div>
        </Col>
        <Col sm="11">
          <Input
            id="type"
            type="select"
            title={$_("query_type")}
            bind:value={queryType}
            required>
            {#each Object.keys(QueryType) as _queryType}
              <option value={_queryType}>{_queryType}</option>
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
      <Col sm="3">
        <Input id="from_date" type="date" title={$_("from")} value={""} /></Col
      >
      <Col sm="3">
        <Input id="to_date" type="date" title={$_("to")} value={""} /></Col
      >
      <Col sm="3">
        <Input id="limit" type="number" title={$_("limit")} value={"10"} /></Col
      >
      <Col sm="">
        <Input
                id="offset"
                type="number"
                title={$_("offset")}
                value={"0"}
        /></Col
      >
    </Row>
  {/if}
  {#if queryType === QueryType.aggregation}
    <Aggregation bind:aggregation_data />
  {/if}
  <Row class="mx-5">
      <Button color="primary" type="submit">{$_("submit")}</Button>
  </Row>
</Form>
