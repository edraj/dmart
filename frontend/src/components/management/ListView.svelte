<script lang="ts">
  import { status_line } from "@/stores/management/status_line.js";
  import {
    Engine,
    functionCreateDatatable,
    Pagination,
    RowsPerPage,
    Sort,
  } from "svelte-datatables-net";
  import { query, QueryType } from "@/dmart";
  import { onDestroy } from "svelte";
  import cols from "@/stores/management/list_cols.json";
  import { search } from "@/stores/management/triggers";
  import Prism from "@/components/Prism.svelte";
  import { goto } from "@roxi/routify";
  import { fade } from "svelte/transition";
  import { isDeepEqual } from "@/utils/compare";
  import {
    Modal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    Button,
  } from "sveltestrap";
  import { params } from "@roxi/routify";

  onDestroy(() => status_line.set(""));

  export let space_name: string;
  export let subpath: string;
  export let shortname: string = null;
  export let type: QueryType = QueryType.search;
  export let columns: any = cols;
  export let is_clickable = true;

  let total: number = 0;
  const { sortBy, sortOrder, page } = $params;
  let objectDatatable = functionCreateDatatable({
    parData: [],
    parSearchableColumns: Object.keys(columns),
    parRowsPerPage: (typeof localStorage !== 'undefined' && localStorage.getItem("rowPerPage") as `${number}`) || "15",
    parSearchString: "",
    parSortBy: sortBy || "shortname",
    parSortOrder: sortOrder || "ascending",
    parActivePage: Number(page) || 1,
  });

  function value(path: string, data, type) {
    if (data===null) {
      return "not_applicable";
    }
    if (path.length == 1 && path[0].length > 0 && path[0] in data) {
      if (type == "json") return JSON.stringify(data[path[0]], undefined, 1);
      else return data[path[0]];
    }

    if (path.length > 1 && path[0].length > 0 && path[0] in data) {
      return value(path.slice(1), data[path[0]], type);
    }
    return "not_applicable";
  }

  let height: number;

  let numberActivePage: number = page || 1;
  let propNumberOfPages: number = 1;
  let numberRowsPerPage: number =
    parseInt(typeof localStorage !==  'undefined' && localStorage.getItem("rowPerPage")) || 15;
  let paginationBottomInfoFrom = 0;
  let paginationBottomInfoTo = 0;
  let sort = {
    sort_by: sortBy || "shortname",
    sort_type: sortOrder || "ascending",
  };

  function setQueryParam(pair: any) {
    const urlSearchParams = new URLSearchParams(window.location.search);
    let href = window.location.pathname + "?";
    
    for (const [k, v] of Object.entries(pair)) {
      if (urlSearchParams.has(k)) {
        urlSearchParams.delete(k);
      }
      if (typeof(v)==="string") {
        urlSearchParams.set(k, v);
      }
    }

    if (window.location.search === "") {
        href += urlSearchParams.toString();
      } else {
        href += "&" + urlSearchParams.toString();
      }

    window.history.pushState({ path: href }, "", href);
  }

  function setNumberOfPages() {
    propNumberOfPages = Math.ceil(total / numberRowsPerPage);
  }

  let old_search = "";
  async function fetchPageRecords(isSetPage = true, requestExtra = {}) {
    const resp = await query({
      filter_shortnames: shortname ? [shortname] : [],
      type,
      space_name: space_name,
      subpath: subpath,
      exact_subpath: true,
      limit: objectDatatable.numberRowsPerPage,
      offset:
        objectDatatable.numberRowsPerPage *
        (objectDatatable.numberActivePage - 1),
      search: $search,
      ...requestExtra,
    });

    old_search = $search;
    total = resp.attributes.total;

    objectDatatable.arrayRawData = resp.records;
    if (isSetPage) {
      if (objectDatatable.arrayRawData.length === 0) {
        propNumberOfPages = 0;
      } else {
        setNumberOfPages();
      }
    }
    if (resp.status === "success") {
      // api_status = "success";
      // status_line.set(
      //   `<small>Loaded: <strong>${objectDatatable.numberRowsPerPage} of ${total}</strong><br/>Api: <strong>${api_status}</strong></small>`
      // );
    } else {
      // api_status = resp.error.message || "Unknown error";
      // status_line.set(`api: ${api_status}`);
    }
  }

  let modalData: any = {};
  let open = false;

  function redirectToEntry(record: any) {
    const shortname = record.shortname;
    const schema_shortname = record.attributes?.payload?.schema_shortname;
    let tmp_subpath = record.subpath.replaceAll("/", "-");

    if (schema_shortname) {
      $goto(
        "/management/content/[space_name]/[subpath]/[shortname]/[resource_type]/[payload_type]/[schema_name]",
        {
          space_name: space_name,
          subpath: tmp_subpath,
          shortname: shortname,
          resource_type: record.resource_type,
          payload_type: record.attributes?.payload?.content_type,
          schema_name: schema_shortname,
        }
      );
    } else {
      $goto(
        "/management/content/[space_name]/[subpath]/[shortname]/[resource_type]",
        {
          space_name: space_name,
          subpath: tmp_subpath,
          shortname: shortname,
          resource_type: record.resource_type,
        }
      );
    }
  }

  async function onListClick(record: any) {
    if (!is_clickable) {
      return;
    }

    if (type === QueryType.events) {
      open = true;

      const blacklist = ["sec", "content-type", "accept", "host", "connection"];
      modalData = JSON.parse(JSON.stringify(record));

      if (modalData?.attributes?.attributes?.request_headers) {
        modalData.attributes.attributes.request_headers = Object.keys(
          modalData.attributes.attributes.request_headers
        ).reduce(
          (acc, key) =>
            blacklist.some((item) => key.includes(item))
              ? acc
              : {
                  ...acc,
                  [key]: modalData.attributes.attributes.request_headers[key],
                },
          {}
        );
      }
      return;
    }

    if (record.resource_type === "folder") {
      let _subpath = `${record.subpath}/${record.shortname}`.replace(
        /\/+/g,
        "/"
      );

      // Trim leading or traling '/'
      if (_subpath.length > 0 && subpath[0] === "/")
        _subpath = _subpath.substring(1);
      if (_subpath.length > 0 && _subpath[_subpath.length - 1] === "/")
        _subpath = _subpath.slice(0, -1);

      $goto("/management/content/[space_name]/[subpath]", {
        space_name: space_name,
        subpath: _subpath.replaceAll("/", "-"),
      });
      return;
    }

    redirectToEntry(record);
  }

  $: {
    if (
      old_search != $search &&
      type !== QueryType.history &&
      objectDatatable
    ) {
      objectDatatable.stringSortBy = "shortname";
      fetchPageRecords(true);
    }
  }

  $: {
    if (objectDatatable === undefined) {
      objectDatatable = functionCreateDatatable({
        parData: [],
        parSearchableColumns: Object.keys(columns),
        parRowsPerPage:
          (typeof localStorage !== 'undefined' && localStorage.getItem("rowPerPage") as `${number}`) || "15",
        parSearchString: "",
        parSortBy: sortBy || "shortname",
        parSortOrder: sortOrder || "ascending",
        parActivePage: Number(page) || 1,
      });
    }
  }

  $: {
    if (objectDatatable) {
      if (
        !isDeepEqual(sort, {
          sort_by: objectDatatable.stringSortBy,
          sort_type: objectDatatable.stringSortOrder,
        })
      ) {
        const x = {
          sort_by: objectDatatable.stringSortBy.toString(),
          sort_type: objectDatatable.stringSortOrder,
        };
        setQueryParam({
          sortBy: objectDatatable.stringSortBy.toString(),
          sortOrder: objectDatatable.stringSortOrder,
        });
        fetchPageRecords(true, x);
        sort = structuredClone(x);
      }
      if (objectDatatable.numberRowsPerPage != numberRowsPerPage) {
        numberRowsPerPage = objectDatatable.numberRowsPerPage;
        if (typeof localStorage !== 'undefined')
          localStorage.setItem("rowPerPage", numberRowsPerPage.toString());
        fetchPageRecords();
      }
      if (objectDatatable.numberActivePage != numberActivePage) {
        setQueryParam({page: objectDatatable.numberActivePage.toString()});
        numberActivePage = objectDatatable.numberActivePage;
        fetchPageRecords(false);
      }

      paginationBottomInfoFrom = objectDatatable.numberRowsPerPage *  (objectDatatable.numberActivePage - 1) + 1;
      paginationBottomInfoTo =
        objectDatatable.numberRowsPerPage * objectDatatable.numberActivePage;
      paginationBottomInfoTo =
        paginationBottomInfoTo >= total ? total : paginationBottomInfoTo;
    }
  }
</script>

{#key open}
  <Modal
    isOpen={open}
    toggle={() => {
      open != open;
    }}
    size={"lg"}
  >
    <ModalHeader toggle={() => (open = false)}
      >{modalData.shortname}</ModalHeader
    >
    <ModalBody>
      <Prism code={modalData} />
    </ModalBody>
    <ModalFooter>
      <Button color="secondary" on:click={() => (open = false)}>Close</Button>
      <Button
        color="primary"
        on:click={() => {
          open = false;
          redirectToEntry(modalData);
        }}>Entry</Button
      >
    </ModalFooter>
  </Modal>
{/key}

<svelte:window bind:innerHeight={height} />

<div class="list">
  {#await fetchPageRecords()}
    READING DATA...
  {:then}
    <Engine bind:propDatatable={objectDatatable} />

    <div class="mx-3" transition:fade={{ delay: 25 }}>
      {#if objectDatatable?.arraySearched.length === 0}
        <div class="text-center pt-5">
          <strong>NO RECORDS FOUND.</strong>
        </div>
      {:else}
        <table class="table table-striped table-sm mt-2">
          <thead>
            <tr>
              {#each Object.keys(columns) as col}
                <th>
                  <Sort bind:propDatatable={objectDatatable} propColumn={col}
                    >{columns[col].title}</Sort
                  >
                </th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each objectDatatable.arrayRawData as row}
              <tr>
                {#each Object.keys(columns) as col}
                  <!-- svelte-ignore a11y-click-events-have-key-events -->
                  <td
                    style="cursor: pointer;"
                    on:click={() => onListClick(row)}
                  >
                    {value(
                      columns[col].path.split("."),
                      row,
                      columns[col].type
                    )}
                  </td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
        <div class="d-flex justify-content-center justify-content-md-end">
          {#key propNumberOfPages}
            <div
              class="d-flex justify-content-between align-items-center w-100"
            >
              <RowsPerPage
                bind:propDatatable={objectDatatable}
                class="d-inline form-select form-select-sm w-auto"
              >
                <option value="15">15</option>
                <option value="30">30</option>
                <option value="50">50</option>
                <option value="100">100</option>
              </RowsPerPage>
              <p class="p-0 m-0">
                Showing {paginationBottomInfoFrom} to {paginationBottomInfoTo}
                of {total} entries
              </p>
              <Pagination
                bind:propDatatable={objectDatatable}
                bind:propNumberOfPages
                maxPageDisplay={5}
                propSize="default"
              />
            </div>
          {/key}
        </div>
      {/if}
    </div>
  {/await}
</div>

<style>
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

  tr:hover > td {
    background-color: rgba(128, 128, 128, 0.266);
  }
</style>
