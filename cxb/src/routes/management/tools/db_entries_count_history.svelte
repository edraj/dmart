<script lang="ts">
    import { Dmart } from "@edraj/tsdmart";
    import { onMount } from "svelte";
    import { goto } from "@roxi/routify";
    import { Spinner, Card } from "flowbite-svelte";
    import {
        ArrowLeftOutline,
        ChartLineUpOutline,
        FolderSolid,
        TableColumnOutline,
        ExpandOutline,
        CloseOutline,
    } from "flowbite-svelte-icons";

    $goto;

    interface HistoryEntry {
        entries_count: number;
        recorded_at: string;
    }

    interface SpaceHistory {
        spacename: string;
        data: HistoryEntry[];
    }

    let isLoading = $state(true);
    let error: string | null = $state(null);
    let spaces: SpaceHistory[] = $state([]);

    // Per-card view mode: "graph" | "table"
    let viewModes: Record<string, "graph" | "table"> = $state({});

    // Fullscreen modal
    let fullscreenSpace: SpaceHistory | null = $state(null);

    function openFullscreen(space: SpaceHistory) {
        fullscreenSpace = space;
    }
    function closeFullscreen() {
        fullscreenSpace = null;
    }
    function onKeydown(e: KeyboardEvent) {
        if (e.key === "Escape") closeFullscreen();
    }

    onMount(async () => {
        try {
            isLoading = true;
            const axiosInstance = Dmart.getAxiosInstance();
            const headers = Dmart.getHeaders();
            const response = await axiosInstance.get(
                "db_entries_count_history/",
                { headers },
            );
            if (response.data?.status === "success") {
                spaces = response.data.data ?? [];
                // Default: graph mode for spaces with ≥2 points, table otherwise
                for (const s of spaces) {
                    viewModes[s.spacename] =
                        s.data?.length >= 2 ? "graph" : "table";
                }
            } else {
                error =
                    response.data?.error?.message ??
                    "Failed to load DB entries count history.";
            }
        } catch (err: any) {
            error =
                err?.message ??
                "An error occurred while fetching DB entries count history.";
        } finally {
            isLoading = false;
        }
    });

    function formatDate(dt: string): string {
        return dt.replace("T", " ");
    }

    function latestCount(space: SpaceHistory): number {
        if (!space.data || space.data.length === 0) return 0;
        return space.data[space.data.length - 1].entries_count;
    }

    function trend(space: SpaceHistory): "up" | "down" | "flat" {
        if (!space.data || space.data.length < 2) return "flat";
        const delta =
            space.data[space.data.length - 1].entries_count -
            space.data[0].entries_count;
        if (delta > 0) return "up";
        if (delta < 0) return "down";
        return "flat";
    }

    // ── SVG chart helpers ──────────────────────────────────────────────────────
    const W = 300;
    const H = 120;
    const PAD = { top: 10, right: 12, bottom: 24, left: 44 };
    const FS_PAD = { top: 10, right: 12, bottom: 24, left: 20 };

    function buildChart(data: HistoryEntry[], pad = PAD) {
        const innerW = W - pad.left - pad.right;
        const innerH = H - pad.top - pad.bottom;

        const counts = data.map((d) => d.entries_count);
        const minY = Math.min(...counts);
        const maxY = Math.max(...counts);
        const rangeY = maxY - minY || 1;

        const scaleX = (i: number) =>
            pad.left + (i / (data.length - 1)) * innerW;
        const scaleY = (v: number) =>
            pad.top + innerH - ((v - minY) / rangeY) * innerH;

        const points = data.map(
            (d, i) => `${scaleX(i)},${scaleY(d.entries_count)}`,
        );
        const polyline = points.join(" ");

        // Fill area under curve
        const areaPoints = [
            `${pad.left},${pad.top + innerH}`,
            ...points,
            `${scaleX(data.length - 1)},${pad.top + innerH}`,
        ].join(" ");

        // Y-axis ticks (3 labels)
        const yTicks = [minY, Math.round((minY + maxY) / 2), maxY];

        // X-axis labels: first and last
        const xLabels = [
            {
                x: scaleX(0),
                label: formatDate(data[0].recorded_at).slice(0, 10),
            },
            {
                x: scaleX(data.length - 1),
                label: formatDate(data[data.length - 1].recorded_at).slice(
                    0,
                    10,
                ),
            },
        ];

        // Dot positions for all points
        const dots = data.map((d, i) => ({
            cx: scaleX(i),
            cy: scaleY(d.entries_count),
            count: d.entries_count,
            label: formatDate(d.recorded_at),
        }));

        return {
            polyline,
            areaPoints,
            yTicks,
            xLabels,
            dots,
            scaleX,
            scaleY,
            minY,
            maxY,
            innerH,
            pad,
        };
    }
</script>

<div class="container mx-auto p-8">
    <button
        class="flex items-center gap-2 text-gray-600 hover:text-primary-600 mb-6 transition-colors"
        onclick={() => $goto("/management/tools")}
    >
        <ArrowLeftOutline size="sm" />
        <span>Back to Tools</span>
    </button>

    <div class="flex items-center gap-3 mb-8">
        <div class="p-3 bg-primary-100 rounded-full">
            <ChartLineUpOutline class="w-8 h-8 text-primary-600" />
        </div>
        <div>
            <h1 class="text-2xl font-bold">DB Entries Count History</h1>
            <p class="text-gray-500">
                Track the growth of entries across spaces over time.
            </p>
        </div>
    </div>

    {#if error}
        <div
            class="p-4 mb-4 text-sm text-red-800 rounded-lg bg-red-50"
            role="alert"
        >
            <span class="font-medium">Error!</span>
            {error}
        </div>
    {/if}

    {#if isLoading}
        <div class="flex justify-center items-center h-64">
            <Spinner size="12" />
        </div>
    {:else if spaces.length === 0 && !error}
        <p class="text-gray-500 text-center mt-16">No data available.</p>
    {:else}
        <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {#each spaces as space}
                {@const t = trend(space)}
                {@const canGraph = space.data?.length >= 2}
                {@const mode = viewModes[space.spacename] ?? "table"}

                <Card class="w-full max-w-none p-0 overflow-hidden">
                    <!-- Header -->
                    <div
                        class="flex items-center justify-between px-5 py-4 border-b border-gray-100 bg-gray-50"
                    >
                        <div class="flex items-center gap-3">
                            <div class="p-2 bg-primary-100 rounded-lg">
                                <FolderSolid class="w-5 h-5 text-primary-600" />
                            </div>
                            <h3
                                class="text-base font-bold truncate max-w-[160px]"
                                title={space.spacename}
                            >
                                {space.spacename}
                            </h3>
                        </div>

                        <div class="flex items-center gap-3">
                            {#if canGraph}
                                <button
                                    class="p-1.5 rounded-lg border border-gray-200 bg-white hover:bg-primary-50 hover:border-primary-300 transition-colors"
                                    title={mode === "graph"
                                        ? "Switch to table"
                                        : "Switch to graph"}
                                    onclick={() => {
                                        viewModes[space.spacename] =
                                            mode === "graph"
                                                ? "table"
                                                : "graph";
                                    }}
                                >
                                    {#if mode === "graph"}
                                        <TableColumnOutline
                                            class="w-4 h-4 text-gray-500"
                                        />
                                    {:else}
                                        <ChartLineUpOutline
                                            class="w-4 h-4 text-gray-500"
                                        />
                                    {/if}
                                </button>

                                {#if mode === "graph"}
                                    <button
                                        class="p-1.5 rounded-lg border border-gray-200 bg-white hover:bg-primary-50 hover:border-primary-300 transition-colors"
                                        title="Fullscreen"
                                        onclick={() => openFullscreen(space)}
                                    >
                                        <ExpandOutline
                                            class="w-4 h-4 text-gray-500"
                                        />
                                    </button>
                                {/if}
                            {/if}

                            <div class="flex flex-col items-end">
                                <span class="text-2xl font-bold text-gray-800"
                                    >{latestCount(space).toLocaleString()}</span
                                >
                                <span class="text-xs text-gray-400"
                                    >entries</span
                                >
                            </div>
                        </div>
                    </div>

                    <!-- Body: graph or table -->
                    {#if mode === "graph" && canGraph}
                        {@const chart = buildChart(space.data)}
                        <div class="px-2 pt-3 pb-1">
                            <svg
                                viewBox="0 0 {W} {H}"
                                width="100%"
                                class="overflow-visible"
                                aria-label="Entries over time"
                            >
                                <!-- Area fill -->
                                <polygon
                                    points={chart.areaPoints}
                                    fill="url(#grad-{space.spacename})"
                                    opacity="0.18"
                                />

                                <!-- Gradient def -->
                                <defs>
                                    <linearGradient
                                        id="grad-{space.spacename}"
                                        x1="0"
                                        y1="0"
                                        x2="0"
                                        y2="1"
                                    >
                                        <stop
                                            offset="0%"
                                            stop-color="#3b82f6"
                                            stop-opacity="1"
                                        />
                                        <stop
                                            offset="100%"
                                            stop-color="#3b82f6"
                                            stop-opacity="0"
                                        />
                                    </linearGradient>
                                </defs>

                                <!-- Y-axis grid lines + labels -->
                                {#each chart.yTicks as tick}
                                    {@const cy = chart.scaleY(tick)}
                                    <line
                                        x1={PAD.left}
                                        y1={cy}
                                        x2={W - PAD.right}
                                        y2={cy}
                                        stroke="#e5e7eb"
                                        stroke-width="1"
                                    />
                                    <text
                                        x={PAD.left - 4}
                                        y={cy + 4}
                                        text-anchor="end"
                                        font-size="9"
                                        fill="#9ca3af"
                                        >{tick.toLocaleString()}</text
                                    >
                                {/each}

                                <!-- Line -->
                                <polyline
                                    points={chart.polyline}
                                    fill="none"
                                    stroke="#3b82f6"
                                    stroke-width="2"
                                    stroke-linejoin="round"
                                    stroke-linecap="round"
                                />

                                <!-- Dots with tooltips -->
                                {#each chart.dots as dot}
                                    <g>
                                        <title
                                            >{dot.label}: {dot.count.toLocaleString()}</title
                                        >
                                        <circle
                                            cx={dot.cx}
                                            cy={dot.cy}
                                            r="3.5"
                                            fill="#ffffff"
                                            stroke="#3b82f6"
                                            stroke-width="2"
                                        />
                                    </g>
                                {/each}

                                <!-- X-axis labels -->
                                {#each chart.xLabels as lbl}
                                    <text
                                        x={lbl.x}
                                        y={H - 4}
                                        text-anchor="middle"
                                        font-size="8"
                                        fill="#9ca3af">{lbl.label}</text
                                    >
                                {/each}
                            </svg>
                        </div>
                    {:else}
                        <!-- Table mode -->
                        <div class="overflow-y-auto max-h-52">
                            {#if space.data && space.data.length > 0}
                                <table
                                    class="w-full text-xs text-left text-gray-600"
                                >
                                    <thead
                                        class="sticky top-0 bg-white border-b border-gray-100 text-gray-400 uppercase"
                                    >
                                        <tr>
                                            <th class="px-4 py-2 font-medium"
                                                >Recorded At</th
                                            >
                                            <th
                                                class="px-4 py-2 font-medium text-right"
                                                >Count</th
                                            >
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {#each [...space.data].reverse() as entry}
                                            <tr
                                                class="border-b border-gray-50 hover:bg-gray-50"
                                            >
                                                <td
                                                    class="px-4 py-2 font-mono text-gray-500"
                                                >
                                                    {formatDate(
                                                        entry.recorded_at,
                                                    )}
                                                </td>
                                                <td
                                                    class="px-4 py-2 text-right font-semibold text-gray-700"
                                                >
                                                    {entry.entries_count.toLocaleString()}
                                                </td>
                                            </tr>
                                        {/each}
                                    </tbody>
                                </table>
                            {:else}
                                <p
                                    class="text-center text-gray-400 py-6 text-xs"
                                >
                                    No history entries.
                                </p>
                            {/if}
                        </div>
                    {/if}

                    <!-- Footer: trend badge -->
                    <div
                        class="px-5 py-3 border-t border-gray-100 flex items-center gap-2"
                    >
                        {#if t === "up"}
                            <span
                                class="inline-flex items-center gap-1 text-xs font-semibold text-green-700 bg-green-50 px-2 py-0.5 rounded-full"
                            >
                                ↑ Growing
                            </span>
                        {:else if t === "down"}
                            <span
                                class="inline-flex items-center gap-1 text-xs font-semibold text-red-700 bg-red-50 px-2 py-0.5 rounded-full"
                            >
                                ↓ Shrinking
                            </span>
                        {:else}
                            <span
                                class="inline-flex items-center gap-1 text-xs font-semibold text-gray-600 bg-gray-100 px-2 py-0.5 rounded-full"
                            >
                                → Stable
                            </span>
                        {/if}
                        <span class="text-xs text-gray-400"
                            >{space.data?.length ?? 0} snapshot(s)</span
                        >
                    </div>
                </Card>
            {/each}
        </div>
    {/if}
</div>

<!-- Fullscreen chart overlay -->
{#if fullscreenSpace}
    {@const fs = fullscreenSpace}
    {@const fsChart = buildChart(fs.data, FS_PAD)}
    {@const fst = trend(fs)}

    <!-- Backdrop -->
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
        class="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex flex-col"
        onclick={(e) => {
            if (e.target === e.currentTarget) closeFullscreen();
        }}
    >
        <!-- Modal panel -->
        <div
            class="relative flex-1 flex flex-col bg-white m-6 rounded-2xl shadow-2xl overflow-hidden"
        >
            <!-- Modal header -->
            <div
                class="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gray-50"
            >
                <div class="flex items-center gap-3">
                    <div class="p-2 bg-primary-100 rounded-lg">
                        <FolderSolid class="w-5 h-5 text-primary-600" />
                    </div>
                    <div>
                        <h2 class="text-lg font-bold">{fs.spacename}</h2>
                        <p class="text-xs text-gray-400">
                            {fs.data.length} snapshot(s)
                        </p>
                    </div>
                </div>

                <div class="flex items-center gap-4">
                    <div class="text-right">
                        <div class="text-3xl font-bold text-gray-800">
                            {latestCount(fs).toLocaleString()}
                        </div>
                        <div class="text-xs text-gray-400">entries</div>
                    </div>
                    {#if fst === "up"}
                        <span
                            class="inline-flex items-center gap-1 text-xs font-semibold text-green-700 bg-green-50 px-2 py-1 rounded-full"
                            >↑ Growing</span
                        >
                    {:else if fst === "down"}
                        <span
                            class="inline-flex items-center gap-1 text-xs font-semibold text-red-700 bg-red-50 px-2 py-1 rounded-full"
                            >↓ Shrinking</span
                        >
                    {:else}
                        <span
                            class="inline-flex items-center gap-1 text-xs font-semibold text-gray-600 bg-gray-100 px-2 py-1 rounded-full"
                            >→ Stable</span
                        >
                    {/if}
                    <button
                        class="p-2 rounded-lg border border-gray-200 bg-white hover:bg-red-50 hover:border-red-300 transition-colors"
                        title="Close (Esc)"
                        onclick={closeFullscreen}
                    >
                        <CloseOutline class="w-5 h-5 text-gray-500" />
                    </button>
                </div>
            </div>

            <!-- Full chart -->
            <div class="flex-1 p-6 overflow-hidden">
                <svg
                    viewBox="0 0 {W} {H}"
                    width="100%"
                    height="100%"
                    preserveAspectRatio="xMidYMid meet"
                    class="overflow-visible"
                    aria-label="Entries over time — fullscreen"
                >
                    <polygon
                        points={fsChart.areaPoints}
                        fill="url(#fs-grad)"
                        opacity="0.15"
                    />
                    <defs>
                        <linearGradient
                            id="fs-grad"
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                        >
                            <stop
                                offset="0%"
                                stop-color="#3b82f6"
                                stop-opacity="1"
                            />
                            <stop
                                offset="100%"
                                stop-color="#3b82f6"
                                stop-opacity="0"
                            />
                        </linearGradient>
                    </defs>

                    {#each fsChart.yTicks as tick}
                        {@const cy = fsChart.scaleY(tick)}
                        <line
                            x1={fsChart.pad.left}
                            y1={cy}
                            x2={W - fsChart.pad.right}
                            y2={cy}
                            stroke="#e5e7eb"
                            stroke-width="0.5"
                        />
                        <text
                            x={fsChart.pad.left - 4}
                            y={cy + 4}
                            text-anchor="end"
                            font-size="7"
                            fill="#9ca3af">{tick.toLocaleString()}</text
                        >
                    {/each}

                    <!-- X-axis tick for every point -->
                    {#each fs.data as entry, i}
                        <text
                            x={fsChart.scaleX(i)}
                            y={H - 2}
                            text-anchor="middle"
                            font-size="4"
                            fill="#d1d5db"
                            >{formatDate(entry.recorded_at).slice(5, 16)}</text
                        >
                    {/each}

                    <polyline
                        points={fsChart.polyline}
                        fill="none"
                        stroke="#3b82f6"
                        stroke-width="1.5"
                        stroke-linejoin="round"
                        stroke-linecap="round"
                    />

                    {#each fsChart.dots as dot}
                        <g>
                            <title
                                >{dot.label}: {dot.count.toLocaleString()}</title
                            >
                            <circle
                                cx={dot.cx}
                                cy={dot.cy}
                                r="3"
                                fill="#fff"
                                stroke="#3b82f6"
                                stroke-width="1.5"
                            />
                        </g>
                    {/each}
                </svg>
            </div>
        </div>
    </div>
{/if}

<svelte:window onkeydown={onKeydown} />
