<script lang="ts">
    import {Engine, functionCreateDatatable, Pagination, RowsPerPage, Sort,} from "svelte-datatables-net";
    import {Dmart, DmartScope, type ApiResponseRecord, type QueryRequest, QueryType, SortyType,} from "@edraj/tsdmart";
    import cols from "@/utils/jsons/list_cols.json";
    import {searchListView} from "@/stores/management/triggers";
    import Prism from "@/components/Prism.svelte";
    import {goto, params} from "@roxi/routify";
    import {fade} from "svelte/transition";
    import {isDeepEqual} from "@/utils/compare";
    import {folderRenderingColsToListCols, type ListColumn} from "@/utils/columnsUtils";
    import {
        Button,
        Checkbox,
        ListPlaceholder,
        Modal,
        Table,
        TableBody,
        TableBodyCell,
        TableBodyRow,
        TableHead,
        TableHeadCell,
    } from "flowbite-svelte";
    import {bulkBucket} from "@/stores/management/bulk_bucket";
    import {spaces} from "@/stores/management/spaces";
    import {getSpaces} from "@/lib/dmart_services";
    import {Level, showToast} from "@/utils/toast";
    import EmptyState from "@/components/ui/EmptyState.svelte";
    import ListViewActionBar from "@/components/management/ListViewActionBar.svelte";
    import {currentListView} from "@/stores/global";
    import {untrack} from "svelte";
    import {getRowsPerPageSetting, getValueByPath} from "@/utils/listViewUtils";
    import {website} from "@/config";

    $goto;

    $bulkBucket = [];

    let {
        space_name = $bindable(),
        subpath = $bindable(),
        shortname = $bindable(null),
        type = $bindable(QueryType.search),
        folderColumns = $bindable(null),
        sort_by = $bindable(null),
        sort_order = $bindable(null),
        query = $bindable(null),
        is_clickable = $bindable(true),
        canDelete = $bindable(false),
        exact_subpath = $bindable(true),
        scope = $bindable(DmartScope.managed),
    }: {
        space_name?: string;
        subpath?: string;
        shortname?: string | null;
        type?: QueryType;
        folderColumns?: any;
        sort_by?: string | null;
        sort_order?: string | null;
        query?: any;
        is_clickable?: boolean;
        canDelete?: boolean;
        exact_subpath?: boolean;
        scope?: DmartScope;
    } = $props();

    $currentListView = {fetchPageRecords};

    let _initColumns: Record<string, ListColumn>;
    if (folderColumns === null || folderColumns.length === 0) {
        _initColumns = cols;
    } else {
        _initColumns = folderRenderingColsToListCols(folderColumns);
    }
    if (Object.keys(_initColumns).includes("undefined")) {
        _initColumns = {
            shortname: {
                path: "shortname",
                title: "shortname",
                type: "string",
                width: "20%",
            },
        };
    }
    let columns: Record<string, ListColumn> | null = $state(_initColumns);

    let total: number | null = $state(null);
    const {sortBy, sortOrder, page, search} = $params;
    if (search) {
        $searchListView = search;
    }
    let sort = {
        sort_by: (sortBy ?? sort_by) || "shortname", // descending
        sort_order: (sortOrder ?? sort_order) || "ascending",
    };

    let objectDatatable = $state(
        functionCreateDatatable({
            parData: [],
            parRowsPerPage:
                (typeof localStorage !== "undefined" &&
                    (localStorage.getItem("rowPerPage") as `${number}`)) ||
                "15",
            parSearchString: "",
            parSortBy: (sortBy ?? sort_by) || "shortname",
            parSortOrder: (sortOrder ?? sort_order) || "ascending",
            parActivePage: Number(page) || 1,
        }),
    );

    $effect(() => {
        if (columns) objectDatatable.arraySearchableColumns = Object.keys(columns);
    });

    let height: number = $state(0);
    let numberActivePage: number = page || 1;
    let propNumberOfPages: number = $state(1);
    let numberRowsPerPage: number = getRowsPerPageSetting();
    let paginationBottomInfoFrom = $derived(
        objectDatatable.numberRowsPerPage * (objectDatatable.numberActivePage - 1) +
        1,
    );
    let paginationBottomInfoTo = $derived(
        objectDatatable.numberRowsPerPage * objectDatatable.numberActivePage >=
        (total ?? 0)
            ? (total ?? 0)
            : objectDatatable.numberRowsPerPage * objectDatatable.numberActivePage,
    );

    function setNumberOfPages() {
        propNumberOfPages = Math.ceil((total ?? 0) / numberRowsPerPage);
        localStorage.setItem("rowPerPage", numberRowsPerPage.toString());
        if (website.delay_total_count) {
            objectDatatable.numberRowsPerPage = numberRowsPerPage;
        }
    }

    let old_search = "";
    let queryObject: any = {};

    async function fetchPageRecordsTotal(query: QueryRequest) {
        query.type = QueryType.counters;
        query.retrieve_total = true;
        const resp = await Dmart.query(query, scope);
        total = resp?.attributes?.total ?? 0;
        objectDatatable.arrayRawData = [...objectDatatable.arrayRawData];
        setNumberOfPages();
    }

    /* Listen for changes to space_name or subpath when component is reused */
    let old_subpath = subpath;
    let old_space_name = space_name;
    $effect(() => {
        if (subpath !== old_subpath || space_name !== old_space_name) {
            untrack(() => {
                objectDatatable.numberActivePage = 1;
                numberActivePage = 1;

                $searchListView = "";
                objectDatatable.stringSortBy = "shortname";
                objectDatatable.stringSortOrder = "ascending";

                let newParams = {...$params};
                delete newParams.page;
                delete newParams.search;
                delete newParams.sortBy;
                delete newParams.sortOrder;
                $goto("$leaf", newParams);

                old_subpath = subpath;
                old_space_name = space_name;

                fetchPageRecords(true, {});
            });
        }
    });

    let isFetching = $state(false);

    async function fetchPageRecords(isSetPage = true, requestExtra = {}) {
        const delayTotalCount = website.delay_total_count === true;

        isFetching = true;
        let _search = $searchListView;

        if (subpath === "/") {
            if ($spaces === null || $spaces.length === 0) {
                await getSpaces();
            }
            const currentSpace = $spaces?.find((e) => e.shortname === space_name);
            const hideFolders = currentSpace?.attributes?.hide_folders;

            if (hideFolders?.length) {
                _search += ` -@shortname:${hideFolders.join("|")}`;
            }
        }

        if (query?.type && query?.search) {
            _search += ` ${query.search.trim()}`;
        }
        let _subpath = (subpath ?? '').replaceAll('-', '/')
        queryObject = {
            filter_shortnames: shortname ? [shortname] : [],
            type,
            space_name: space_name,
            subpath: _subpath,
            exact_subpath: exact_subpath,
            limit: objectDatatable.numberRowsPerPage,
            sort_by: (objectDatatable.stringSortBy ?? "shortname").toString(),
            sort_type: SortyType[objectDatatable.stringSortOrder],
            offset:
                objectDatatable.numberRowsPerPage *
                (objectDatatable.numberActivePage - 1),
            search: _search.trim(),
            ...requestExtra,
            retrieve_json_payload: true,
            retrieve_total: !delayTotalCount,
        };
        if ($currentListView) {
            $currentListView.query = queryObject;
        }
        if (delayTotalCount) {
            fetchPageRecordsTotal({...queryObject});
        }
        const resp = await Dmart.query({...queryObject}, scope);

        old_search = $searchListView;
        if (delayTotalCount === false) {
            total = resp?.attributes?.total ?? 0;
        } else {
            total = -1;
        }
        objectDatatable.arrayRawData = (resp?.records ?? []) as any;
        if (isSetPage) {
            if (objectDatatable.arrayRawData.length === 0) {
                propNumberOfPages = 0;
            } else {
                if (delayTotalCount === false) {
                    setNumberOfPages();
                }
            }
        }
        isFetching = false;
    }

    let modalData: any = $state({});
    let open = $state(false);

    async function onListClick(event: any, record: any) {
        if (!is_clickable) {
            return;
        }

        if (type === QueryType.events) {
            open = true;

            const blacklist = ["sec", "content-type", "accept", "host", "connection"];
            modalData = structuredClone(record);

            if (modalData?.attributes?.attributes?.request_headers) {
                modalData.attributes.attributes.request_headers = Object.keys(
                    modalData.attributes.attributes.request_headers,
                ).reduce(
                    (acc, key) =>
                        blacklist.some((item) => key.includes(item))
                            ? acc
                            : {
                                ...acc,
                                [key]: modalData.attributes.attributes.request_headers[key],
                            },
                    {},
                );
            }
            return;
        }

        if (record.resource_type === "folder") {
            let _subpath = `${record.subpath}/${record.shortname}`.replace(
                /\/+/g,
                "/",
            );

            if (_subpath.length > 0 && subpath?.[0] === "/") {
                _subpath = _subpath.substring(1);
            }
            if (_subpath.length > 0 && _subpath[_subpath.length - 1] === "/") {
                _subpath = _subpath.slice(0, -1);
            }

            $goto("/management/content/[space_name]/[subpath]", {
                space_name: space_name ?? "",
                subpath: _subpath.replaceAll("/", "-"),
            });

            return;
        }

        redirectToEntry(record);
    }

    /**
     * Sets query parameters for navigation
     */
    export function setQueryParam(params: any) {
        $goto("$leaf", {...params});
    }

    /**
     * Redirects to entry detail page
     */
    export function redirectToEntry(record: any) {
        const shortname = record.shortname;
        const tmp_subpath = record.subpath.replaceAll("/", "-");

        $goto(
            "/management/content/[space_name]/[subpath]/[shortname]/[resource_type]",
            {
                space_name: space_name ?? "",
                subpath: tmp_subpath,
                shortname: shortname,
                resource_type: record.resource_type,
            },
        );
    }

    $effect(() => {
        if (objectDatatable) {
            if (
                !isDeepEqual(sort, {
                    sort_by: objectDatatable.stringSortBy,
                    sort_order: objectDatatable.stringSortOrder,
                })
            ) {
                const x = {
                    sort_by: (objectDatatable.stringSortBy ?? "shortname").toString(),
                    sort_order: objectDatatable.stringSortOrder,
                };
                setQueryParam({
                    ...$params,
                    sortBy: (objectDatatable.stringSortBy ?? "shortname").toString(),
                    sortOrder: objectDatatable.stringSortOrder,
                });

                untrack(() => {
                    fetchPageRecords(true, {
                        sort_by: (objectDatatable.stringSortBy ?? "shortname").toString(),
                        sort_type: objectDatatable.stringSortOrder,
                    });
                });
                sort = structuredClone(x);
            }
        }
    });

    $effect(() => {
        if (objectDatatable.numberRowsPerPage !== numberRowsPerPage) {
            numberRowsPerPage = objectDatatable.numberRowsPerPage;
            if (typeof localStorage !== "undefined") {
                localStorage.setItem("rowPerPage", numberRowsPerPage.toString());
            }
            (async () => {
                try {
                    await fetchPageRecords(true, {});
                    handleAllBulk(null, isAllBulkChecked);
                } catch (e) {
                    showToast(Level.warn, "Failed to fetch records after changing page size");
                }
            })();
        }
    });

    $effect(() => {
        if (objectDatatable.numberActivePage !== numberActivePage) {
            numberActivePage = objectDatatable.numberActivePage;
            untrack(() => {
                setQueryParam({
                    ...$params,
                    page: objectDatatable.numberActivePage.toString(),
                });
            });
        }
    });

    const toggleModal = () => {
        open = !open;
    };

    function handleBulk(event: any) {
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        try {
            const {name, checked} = event.target;
            const record = objectDatatable.arrayRawData[name] as ApiResponseRecord;
            if (checked) {
                $bulkBucket = [
                    ...$bulkBucket,
                    {
                        ...record,
                        shortname: record.shortname,
                        resource_type: record.resource_type,
                    },
                ];
            } else {
                $bulkBucket = $bulkBucket.filter(
                    (e) => e.shortname !== record.shortname,
                );
            }
        } catch (e: any) {
            showToast(Level.warn, "Error processing bulk selection");
            if (e?.target) e.target.checked = false;
        }
    }

    let isAllBulkChecked = false;

    function handleAllBulk(e: any, override: boolean | null = null) {
        isAllBulkChecked = override === null ? !isAllBulkChecked : override;
        if (e) {
            e.target.checked = isAllBulkChecked;
        }

        if (isAllBulkChecked) {
            // Select all — build the full list in one pass
            $bulkBucket = objectDatatable.arrayRawData.map((row: any) => ({
                shortname: row.shortname,
                resource_type: row.resource_type,
                ...row,
            }));
        } else {
            // Deselect all
            $bulkBucket = [];
        }
    }

    function handleSortRendered(node) {
        const timer = setTimeout(() => {
            const spanButton = node.querySelector(
                'span[role="button"][style*="cursor:pointer"][style*="white-space: nowrap"]',
            );
            if (spanButton) {
                spanButton.style.cssText =
                    "cursor:pointer;display:inline-flex;align-items:center;gap:0.375rem;white-space:nowrap;";

                const svgs = spanButton.querySelectorAll("svg");
                svgs.forEach((svg: SVGElement) => {
                    svg.classList.add("text-[color:var(--color-text-muted)]");
                    svg.setAttribute("width", "14");
                    svg.setAttribute("height", "14");
                });
            }
        }, 0);

        return {
            destroy() {
                clearTimeout(timer);
            },
        };
    }

    function cellText(row: any, col: string): string {
        const raw = getValueByPath(
            columns?.[col]?.path?.split(".") ?? [],
            row,
            columns?.[col]?.type ?? "string",
        );
        if (raw === null || raw === undefined) return "";
        return typeof raw === "string" ? raw : String(raw);
    }

    fetchPageRecords(true, {});
</script>

<Modal bind:open size={"lg"}>
    <!--    <ModalHeader toggle={toggleModal}>{}</ModalHeader>-->

    <div class="modal-header">
        <h5 class="modal-title">
            {modalData.shortname}
        </h5>
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <button
                type="button"
                onclick={toggleModal}
                class="btn-close"
                aria-label="Close"
        >
        </button>
    </div>

    <div>
        <Prism code={modalData}/>
    </div>
    <div>
        <Button color="secondary" onclick={() => (open = false)}>Close</Button>
        <Button
                color="primary"
                onclick={() => {
        open = false;
        redirectToEntry(modalData);
      }}>Entry
        </Button
        >
    </div>
</Modal>

<svelte:window bind:innerHeight={height}/>

{#if type !== QueryType.events}
    <ListViewActionBar space_name={space_name ?? ""} subpath={subpath ?? ""}/>
{/if}

{#if isFetching}
    <div class="flex flex-col w-full">
        <ListPlaceholder class="m-5" size="lg" style="width: 100vw"/>
    </div>
{:else}
    <div class="w-full">
        {#if total === null}
            <ListPlaceholder class="m-5" size="lg" style="width: 100vw"/>
        {:else}
            {#if objectDatatable}
                <Engine bind:propDatatable={objectDatatable}/>
            {/if}
            <div class="mx-3" transition:fade={{ delay: 25 }}>
                {#if objectDatatable?.arraySearched.length === 0}
                    <div class="py-6">
                        <EmptyState
                            title="No records found"
                            hint={$searchListView
                                ? "Try clearing the search or adjusting filters."
                                : "This folder is empty. Create a new entry to get started."}
                        />
                    </div>
                {:else}
                    <div class="rounded-[var(--radius-md)] border border-[color:var(--color-border)] overflow-x-auto mt-2 shadow-[var(--shadow-card)]">
                    <Table
                            striped={true}
                            class="border-collapse w-full"
                    >
                        <TableHead class="bg-[color:var(--color-surface)] text-[color:var(--color-text-muted)]">
                            {#if canDelete}
                                <TableHeadCell class="p-2 border-b border-[color:var(--color-border)] w-10">
                                    <Checkbox class="bg-[color:var(--color-bg)]" onchange={handleAllBulk}/>
                                </TableHeadCell>
                            {/if}
                            {#each Object.keys(columns ?? {}) as col}
                                <TableHeadCell class="p-2 border-b border-[color:var(--color-border)] font-semibold text-xs uppercase tracking-wide">
                                    <div use:handleSortRendered>
                                        <Sort bind:propDatatable={objectDatatable} propColumn={col}>
                                            {columns?.[col]?.title}
                                        </Sort>
                                    </div>
                                </TableHeadCell>
                            {/each}
                        </TableHead>
                        <TableBody>
                            {#each objectDatatable.arrayRawData as row, index}
                                {@const typedRow = row as any}
                                <TableBodyRow
                                        class="hover:bg-[color:var(--color-surface-hover)] transition-colors"
                                        onclick={(e) => onListClick(e, typedRow)}
                >
                                    <div style="all: unset;display: contents;">
                                        {#if canDelete}
                      <!-- svelte-ignore a11y_no_static_element_interactions -->
                      <!-- svelte-ignore a11y_click_events_have_key_events -->
                      <span
                              style="all: unset;display: contents;"
                              role="presentation"
                              onclick={(e) => {
                          e.stopPropagation();
                          const checkbox = e.currentTarget.querySelector(
                            'input[type="checkbox"]',
                          ) as HTMLInputElement | null;
                          if (checkbox) {
                            checkbox.checked = !checkbox.checked;
                            const event = new Event("change", {
                              bubbles: true,
                            });
                            checkbox.dispatchEvent(event);
                          }
                        }}
                      >
                        <TableBodyCell class="p-2 border-b border-[color:var(--color-border)]">
                          <Checkbox
                                  class="bg-[color:var(--color-bg)]"
                                  id={typedRow.shortname}
                                  name={index.toString()}
                                  checked={$bulkBucket.some(
                              (e) => e.shortname === typedRow.shortname,
                            )}
                                  onchange={handleBulk}
                                  onclick={(e) => e.stopPropagation()}
                          />
                        </TableBodyCell>
                      </span>
                                        {/if}
                                        {#each Object.keys(columns ?? {}) as col}
                                            {@const value = cellText(typedRow, col)}
                                            <TableBodyCell
                                                    class="p-2 border-b border-[color:var(--color-border)] cursor-pointer max-w-xs"
                                            >
                                                <span class="block truncate" title={value}>{value}</span>
                                            </TableBodyCell>
                                        {/each}
                                    </div>
                                </TableBodyRow>
                            {/each}
                        </TableBody>
                    </Table>
                    </div>
                    <div
                            class="flex flex-col md:flex-row justify-between items-center gap-2 mt-4"
                    >
                        <RowsPerPage
                                bind:propDatatable={objectDatatable}
                                class="form-select form-select-sm w-auto"
                        >
                            <option value="15">15</option>
                            <option value="30">30</option>
                            <option value="50">50</option>
                            <option value="100">100</option>
                        </RowsPerPage>
                        <p class="text-sm text-[color:var(--color-text-muted)]">
                            Showing {paginationBottomInfoFrom} to {paginationBottomInfoTo} of {total}
                            entries
                        </p>
                        {#key propNumberOfPages}
                            <Pagination
                                    bind:propDatatable={objectDatatable}
                                    bind:propNumberOfPages
                                    maxPageDisplay={5}
                                    propSize="default"
                            />
                        {/key}
                    </div>
                {/if}
            </div>
        {/if}
    </div>
{/if}
