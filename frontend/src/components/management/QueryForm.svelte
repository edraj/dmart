<script lang="ts">
  import Input from "../Input.svelte";
  import { _ } from "@/i18n";
  import {
    type QueryRequest,
    QueryType,
    ResourceType,
    csv,
    get_children,
    get_spaces,
    query,
  } from "@/dmart";
  import { createEventDispatcher, onMount } from "svelte";
  import { Button, Col, Row, Form } from "sveltestrap";
  import downloadFile from "@/utils/downloadFile";
  import { Level, showToast } from "@/utils/toast";

  const dispatch = createEventDispatcher();
  let spaces = $state([]);

  onMount(() => {
    async function setup() {
      spaces = (await get_spaces()).records;
    }
    setup();
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
      search,
      offset,
      limit,
    };
    if (from_date) {
      query_request.from_date = `${from_date}T00:00:00.000Z`;
    }
    if (to_date) {
      query_request.from_date = `${to_date}T00:00:00.000Z`;
    }
    const response = await query(query_request);
    dispatch("response", response);
  }

  let spacename = $state("management");
  let subpath = $state("/");
  let tempSubpaths = $state([]);
  let subpaths = $state([{ records: [{ shortname: "/", resource_type: "folder" }] }]);

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
  $effect(() => {
    if (spacename) {
      subpaths = [];
      (async () => {
        const _subpaths = await get_children(spacename, subpath);
        await buildSubpaths("", _subpaths);
        subpaths = [...tempSubpaths];
      })();
    }
  });

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
      search: search,
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
  <Input id="type" type="select" title={$_("query_type")} value="search">
    {#each Object.keys(QueryType) as queryType}
      <option value={queryType}>{queryType}</option>
    {/each}
  </Input>
  <Input
    id="space_name"
    type="select"
    title={$_("space_name")}
    bind:value={spacename}
  >
    {#each spaces as space}
      <option value={space.shortname}>{space.shortname}</option>
    {/each}
  </Input>
  <Input id="subpath" type="select" title={$_("subpath")} bind:value={subpath}>
    {#each subpaths as subpath}
      <option value={subpath}>{subpath}</option>
    {/each}
  </Input>
  <Input id="search" type="text" title={$_("search")} value="" />
  <Input id="resource_type" type="select" title={$_("resource_types")}>
    {#each Object.keys(ResourceType) as resourceType}
      <option value={resourceType}>{resourceType}</option>
    {/each}
  </Input>
  <Input id="resource_shortnames" type="text" title={$_("shortnames")} />
  <Input id="from_date" type="date" title={$_("from")} value={""} />
  <Input id="to_date" type="date" title={$_("to")} value={""} />
  <Input id="limit" type="number" title={$_("limit")} value={"10"} />
  <Input id="offset" type="number" title={$_("offset")} value={"0"} />
  <Input
    id="retrieve_attachments"
    type="checkbox"
    title={$_("retrieve_attachments")}
  />
  <Input
    id="retrieve_json_payload"
    type="checkbox"
    title={$_("retrieve_json_payload")}
  />

  <Row form={true}>
    <Col class="d-flex justify-content-between">
      <Button outline type="submit">{$_("submit")}</Button>
      {#if formData}
        <Button outline type="button" onclick={handleDownload}
          >{$_("download_csv")}</Button
        >
      {/if}
    </Col>
  </Row>
</Form>
