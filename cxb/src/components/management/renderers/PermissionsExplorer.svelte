<script lang="ts">
    import { Card } from "flowbite-svelte";
    import { Dmart, ResourceType } from "@edraj/tsdmart";
    import MetaPermissionForm from "@/components/management/forms/MetaPermissionForm.svelte";
    import SpaceMapView from "@/components/management/renderers/SpaceMapView.svelte";
    import { goto } from "@roxi/routify";

    $goto;

    const { permissions, showTabs = true } = $props();

    // ── View mode ──────────────────────────────────────────────────────────────
    let viewMode: "list" | "map" = $state("list");

    // ── Navigation helper ──────────────────────────────────────────────────────
    function handleGoToPermission(e, permission) {
        e.preventDefault();
        $goto(
            `/management/content/[space_name]/[subpath]/[shortname]/[resource_type]`,
            {
                space_name: "management",
                subpath: "permissions",
                shortname: permission,
                resource_type: "permission",
            },
        );
    }

    // ── Map view data ──────────────────────────────────────────────────────────
    type SubpathInfo = {
        resource_types: string[];
        actions: string[];
        conditions: string[];
        allowed_fields_values: Record<string, unknown>;
        filter_fields_values: string;
    };
    type SpaceMap = Record<string, Record<string, SubpathInfo>>;

    let spaceMap: SpaceMap = $state({});
    let mapLoading = $state(false);
    let mapBuilt = $state(false);

    function mergePermission(permission: any) {
        const subpaths: Record<string, string[]> = permission.subpaths ?? {};
        const resourceTypes: string[] = permission.resource_types ?? [];
        const actions: string[] = permission.actions ?? [];
        const conditions: string[] = permission.conditions ?? [];
        const allowedFieldsValues: Record<string, unknown> =
            permission.allowed_fields_values ?? {};
        const filterFieldsValues: string =
            permission.filter_fields_values ?? "";

        for (const [space, paths] of Object.entries(subpaths)) {
            if (!spaceMap[space]) spaceMap[space] = {};
            for (const subpath of paths as string[]) {
                if (!spaceMap[space][subpath]) {
                    spaceMap[space][subpath] = {
                        resource_types: [],
                        actions: [],
                        conditions: [],
                        allowed_fields_values: {},
                        filter_fields_values: "",
                    };
                }
                const info = spaceMap[space][subpath];
                for (const rt of resourceTypes) {
                    if (!info.resource_types.includes(rt))
                        info.resource_types.push(rt);
                }
                for (const act of actions) {
                    if (!info.actions.includes(act)) info.actions.push(act);
                }
                for (const cond of conditions) {
                    if (!info.conditions.includes(cond))
                        info.conditions.push(cond);
                }
                if (Object.keys(allowedFieldsValues).length > 0) {
                    info.allowed_fields_values = {
                        ...info.allowed_fields_values,
                        ...allowedFieldsValues,
                    };
                }
                if (filterFieldsValues) {
                    info.filter_fields_values = info.filter_fields_values
                        ? info.filter_fields_values + " | " + filterFieldsValues
                        : filterFieldsValues;
                }
            }
        }
        spaceMap = { ...spaceMap };
    }

    async function buildMap() {
        if (mapBuilt) return;
        mapLoading = true;
        spaceMap = {};

        for (const permName of permissions) {
            try {
                const perm = await Dmart.retrieveEntry({
                    resource_type: ResourceType.permission,
                    space_name: "management",
                    subpath: "permissions",
                    shortname: permName,
                    retrieve_json_payload: true,
                    retrieve_attachments: false,
                    validate_schema: true,
                });
                mergePermission(perm);
            } catch (e) {
                console.warn(`Could not load permission ${permName}:`, e);
            }
        }

        mapLoading = false;
        mapBuilt = true;
    }

    $effect(() => {
        if (viewMode === "map") {
            buildMap();
        }
    });
</script>

<Card class="w-full max-w-4xl mx-auto p-4 my-2">
    <!-- Tab buttons (suppressed when nested inside another explorer) -->
    {#if showTabs}
        <div class="flex gap-2 mb-4 border-b border-gray-200 pb-2">
            <button
                class="px-4 py-1.5 rounded-t text-sm font-medium transition-colors {viewMode ===
                'list'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'}"
                onclick={() => (viewMode = "list")}
            >
                List
            </button>
            <button
                class="px-4 py-1.5 rounded-t text-sm font-medium transition-colors {viewMode ===
                'map'
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'}"
                onclick={() => (viewMode = "map")}
            >
                Map
            </button>
        </div>
    {/if}

    <!-- List view (original) -->
    {#if viewMode === "list"}
        {#each permissions as permission}
            <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
            <!-- svelte-ignore a11y_click_events_have_key_events -->
            <p
                onclick={(e) => handleGoToPermission(e, permission)}
                class="text-4xl cursor-pointer"
            >
                {permission}
            </p>
            {#await Dmart.retrieveEntry( { resource_type: ResourceType.permission, space_name: "management", subpath: "permissions", shortname: permission, retrieve_json_payload: true, retrieve_attachments: false, validate_schema: true }, ) then _role}
                {@const _noop = () => true}
                <MetaPermissionForm
                    formData={_role}
                    readOnly={true}
                    validateFn={_noop}
                />
            {/await}
        {/each}
    {/if}

    <!-- Map view -->
    {#if viewMode === "map"}
        <SpaceMapView {spaceMap} loading={mapLoading} />
    {/if}
</Card>
