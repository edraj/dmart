<script lang="ts">
  import { status_line } from "@/stores/management/status_line.js";
  import {
    Engine,
    functionCreateDatatable,
    Pagination,
    RowsPerPage,
  } from "svelte-datatables-net";
  import { query, QueryType } from "@/dmart";
  import { onDestroy } from "svelte";
  import { fade } from "svelte/transition";
  import { isDeepEqual } from "@/utils/compare";
  import columns from "@/stores/management/list_cols_history.json";

  onDestroy(() => status_line.set(""));

  let {
      space_name,
      subpath,
      shortname = null,
      type = QueryType.search
  } : {
      space_name: string,
      subpath: string,
      shortname?: string,
      type?: QueryType
  } = $props();

  let total: number = $state(0);

  let objectDatatable = $state(
      functionCreateDatatable({
        parData: [],
        parSearchableColumns: Object.keys(columns),
        parRowsPerPage: (typeof localStorage !== 'undefined' && localStorage.getItem("rowPerPage") as `${number}`) || "15",
        parSearchString: "",
        parSortBy: "shortname",
        parSortOrder: "ascending",
      })
  );

  function parseRequestHeader(data) {
    if (data === undefined) {
      return {};
    }

    const blacklist = ["sec", "content-type", "accept", "host", "connection"];
    return Object.keys(data).reduce(
      (acc, key) =>
        blacklist.some((item) => key.includes(item))
          ? acc
          : { ...acc, [key]: data[key] },
      {}
    );
  }
  function parseDiff(data): any {
    if (data === undefined) {
      return {};
    }
    const blacklist = ["x_request_data"];
    return Object.keys(data).reduce(
      (acc, key) =>
        blacklist.some((item) => key.includes(item))
          ? acc
          : { ...acc, [key]: data[key] },
      {}
    );
  }

  let height: number = $state();

  let numberActivePage = 1;
  let propNumberOfPages = $state(1);
  let numberRowsPerPage: number =
    parseInt(typeof localStorage !== 'undefined' && localStorage.getItem("rowPerPage")) || 15;

  function setNumberOfPages() {
    propNumberOfPages = Math.ceil(total / numberRowsPerPage);
  }

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
      search: "",
      ...requestExtra,
    });

    total = resp.attributes.total;

    objectDatatable.arrayRawData = resp.records;
    if (isSetPage) {
      if (objectDatatable.arrayRawData.length === 0) {
        propNumberOfPages = 0;
      } else {
        setNumberOfPages();
      }
    }
  }

  let paginationBottomInfoFrom = $state(0);
  let paginationBottomInfoTo = $state(0);
  let sort = {
    sort_by: "shortname",
    sort_type: "ascending",
  };

  // Helper function to format values for display in the UI
  function formatValueForDisplay(
    v: any,
    key: string
  ) {
    if(typeof (v[key]) === "object") {
      return JSON.stringify(v[key]);
    }
    return v[key] || "";
  }
</script>

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
            <tr style="text-align: center">
              <th style="width: 20%">Information</th>
              <th style="width: 20%">Request Headers</th>
              <th>DIFF</th>
            </tr>
          </thead>
          <tbody>
            {#each objectDatatable.arrayRawData as row}
              <tr>
                <td>
                  <ul>
                    <li>
                      <b>Owner shortname: </b><br>{row["attributes"][
                        "owner_shortname"
                      ]}
                    </li>
                    <li>
                      <b>Timestamp: </b><br>{row["attributes"]["timestamp"]}
                    </li>
                  </ul>
                </td>
                <td>
                  <ul>
                    {#each Object.entries(parseRequestHeader(row["attributes"]["request_headers"])) as [k, v]}
                      <li><b>{k}: </b><br>{v}</li>
                    {/each}
                  </ul>
                </td>
                <td>
                  {#each Object.entries(parseDiff(row["attributes"]["diff"])) as [k, v]}
                    <ul>
                      <li><b>Field: </b><br>{k}</li>
                      <li>
                        <b
                          >Old:
                        </b><br>{formatValueForDisplay(
                          v,
                          "old"
                      )}
                      </li>
                      <li>
                        <b
                          >New:
                        </b><br>{formatValueForDisplay(
                          v,
                          "new"
                      )}
                      </li>
                    </ul>
                  {/each}
                </td>
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

  table,
  th,
  td {
    padding: 10px;
    border: 1px solid black;
    border-collapse: collapse;
    overflow-wrap: anywhere;
  }
  th {
    vertical-align: middle;
  }

  tr:hover > td {
    background-color: rgba(128, 128, 128, 0.266);
  }
  ul {
    list-style: none;
    padding: 0px;
  }
</style>
