<script lang="ts">
    import {Dmart, QueryType, SortyType} from "@edraj/tsdmart";
    import {ListPlaceholder, Modal, Table} from "flowbite-svelte";
    import {onMount} from "svelte";
    import Prism from "../Prism.svelte";

    let { space_name, subpath, shortname }: { space_name:string, subpath:string, shortname:string } = $props();

  let records = $state([]);
  let loading = $state(true);
  let limit = $state(10);
  let offset = $state(0);
  let totalItems = $state(0);
  let showModal = $state(false);
  let modalData: any = $state(null);

  async function fetchHistory() {
    loading = true;
    try {
      const response = await Dmart.query({
        type: QueryType.history,
        filter_shortnames: shortname ? [shortname] : [],
        space_name,
        subpath,
        search: '',
        limit,
        offset,
        sort_by: 'timestamp',
        sort_type: SortyType.descending
      });
      records = response.records || [];
      // Fix for total_count error
      totalItems = response.attributes.total || records.length;
    } catch (error) {
      console.error('Failed to fetch history:', error);
    } finally {
      loading = false;
    }
  }

  function handlePageChange(event) {
    offset = event.detail.page * limit;
    fetchHistory();
  }

  function changeLimit(newLimit) {
    limit = newLimit;
    offset = 0;
    fetchHistory();
  }

  onMount(fetchHistory);

  function formatKey(key) {
    return key.split('.').map(part =>
            part.charAt(0).toUpperCase() + part.slice(1)
    ).join(' > ');
  }

  function handleModalDetails(value) {
    modalData = value;
    showModal = true;
  }
  function closeModal() {
    showModal = false;
    modalData = null;
  }
</script>

{#if loading}
  <ListPlaceholder class="m-5" size="lg" style="width: 100%"/>
{:else}
  <div class="p-6 bg-white border border-gray-200 rounded-lg shadow-sm dark:bg-gray-800 dark:border-gray-700 w-full">
  {#each records as record, i}

      <div class="flex justify-between mt-4 mb-2">
        <p class="text-lg">
          <strong>By: </strong> {record.attributes?.owner_shortname || 'Unknown'}
        </p>
        <p class="text-lg">
          <strong>At: </strong> {new Date(record.attributes?.timestamp).toLocaleString()}
        </p>
      </div>

      {#if record.attributes?.diff && Object.keys(record.attributes.diff).length > 0}
        <div class="border rounded-lg overflow-hidden">
          <Table class="w-full table-fixed">
            <thead>
            <tr>
              <th class="px-4 py-2 w-[20%]">Property</th>
              <th class="px-4 py-2 w-[40%]">Previous Value</th>
              <th class="px-4 py-2 w-[40%]">New Value</th>
            </tr>
            </thead>
            <tbody>
            {#each Object.entries(record.attributes.diff) as [key, change]}
              {@const typedChange = change as {old?: any, new?: any}}
              <tr class="border-b hover:bg-gray-50">
                <td class="px-4 py-2 font-medium">{formatKey(key)}</td>
                <td class="px-4 py-2 bg-red-50 whitespace-normal cursor-pointer" onclick={() => handleModalDetails(typedChange?.old)}>
                  <span class="text-red-600 font-bold block break-words">{JSON.stringify(typedChange?.old) || ''}</span>
                </td>
                <td class="px-4 py-2 bg-green-50 whitespace-normal cursor-pointer" onclick={() => handleModalDetails(typedChange?.new)}>
                  <span class="text-green-600 font-bold block break-words">{JSON.stringify(typedChange?.new) || ''}</span>
                </td>
              </tr>
            {/each}
            </tbody>
          </Table>
        </div>
      {:else}
        <div class="text-center py-4 text-gray-500">No changes recorded</div>
      {/if}

  {/each}
    <div class="flex flex-col sm:flex-row justify-between my-6">
      <div class="mb-2 sm:mb-0">
        <span class="mr-2">Items per page:</span>
        <div class="inline-flex space-x-1">
          {#each [5, 10, 25, 50] as pageSize}
            <button
                    class="px-3 py-1 text-sm rounded {limit === pageSize ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-800 dark:bg-gray-700 dark:text-gray-200'}"
                    onclick={() => changeLimit(pageSize)}
            >
              {pageSize}
            </button>
          {/each}
        </div>
      </div>

      <div class="flex items-center space-x-2">
      <span class="text-sm text-gray-700 dark:text-gray-300">
    {Math.floor(offset / limit) + 1} of {Math.ceil(totalItems / limit)} pages
  </span>

        <div class="flex space-x-1">
          <button
                  class="px-2 py-1 rounded {offset === 0 ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : 'bg-gray-200 text-gray-800 hover:bg-gray-300 dark:bg-gray-700 dark:text-gray-200'}"
                  disabled={offset === 0}
                  onclick={() => {
        offset = Math.max(0, offset - limit);
        fetchHistory();
      }}
          >
            &lt; Prev
          </button>

          {#each Array(Math.min(5, Math.ceil(totalItems / limit))) as _, pageIndex}
            {@const startPage = Math.max(0, Math.min(Math.floor(offset / limit) - 2, Math.ceil(totalItems / limit) - 5))}
            {@const currentPageIndex = startPage + pageIndex}
            {@const isCurrentPage = Math.floor(offset / limit) === currentPageIndex}
            <button
                    class="px-3 py-1 rounded {isCurrentPage ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-800 hover:bg-gray-300 dark:bg-gray-700 dark:text-gray-200'}"
                    onclick={() => {
          offset = currentPageIndex * limit;
          fetchHistory();
        }}
            >
              {currentPageIndex + 1}
            </button>
          {/each}

          <button
                  class="px-2 py-1 rounded {offset + limit >= totalItems ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : 'bg-gray-200 text-gray-800 hover:bg-gray-300 dark:bg-gray-700 dark:text-gray-200'}"
                  disabled={offset + limit >= totalItems}
                  onclick={() => {
        offset = Math.min(totalItems - limit, offset + limit);
        fetchHistory();
      }}
          >
            Next &gt;
          </button>
        </div>
      </div>
    </div>
  </div>
  {#if records.length === 0}
    <div class="text-center py-8 text-gray-500">No history records found</div>
  {/if}

    <Modal bind:open={showModal} class="pt-8">
        <Prism language="json" code={modalData} />
    </Modal>

{/if}