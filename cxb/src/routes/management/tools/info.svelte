<script lang="ts">
    import {Dmart} from "@edraj/tsdmart";
    import Table2Cols from "@/components/management/Table2Cols.svelte";
    import {InfoCircleOutline, UserSettingsOutline} from "flowbite-svelte-icons";
    import {onMount} from "svelte";

    const TabMode = {
        settings: "settings",
        manifest: "manifest",
    }

    let activeTab = $state(TabMode.settings);
    let settings = $state({});
    let manifest = $state({});
    onMount(async()=>{
        const _settings = await Dmart.getSettings();
        if(_settings.status === "success") {
            settings = _settings.attributes;
        }
        const _manifest = await Dmart.getManifest();
        if(_manifest.status === "success") {
            manifest = _manifest.attributes;
        }
    })

</script>

<div class="border-b border-gray-200">
    <ul class="flex flex-wrap -mb-px text-sm font-medium text-center" role="tablist">
        <li class="mr-2" role="presentation">
            <button
                    class="inline-flex items-center p-4 border-b-2 rounded-t-lg {activeTab === TabMode.settings ? 'text-blue-600 border-blue-600' : 'border-transparent hover:text-gray-600 hover:border-gray-300'}"
                    type="button"
                    role="tab"
                    aria-selected={activeTab === TabMode.settings}
                    onclick={() => activeTab = TabMode.settings}
            >
                <div class="flex items-center gap-2">
                    <UserSettingsOutline size="md" />
                    <p>Settings</p>
                </div>
            </button>
        </li>
        <li class="mr-2" role="presentation">
            <button
                    class="inline-flex items-center p-4 border-b-2 rounded-t-lg {activeTab === TabMode.manifest ? 'text-blue-600 border-blue-600' : 'border-transparent hover:text-gray-600 hover:border-gray-300'}"
                    type="button"
                    role="tab"
                    aria-selected={activeTab === TabMode.manifest}
                    onclick={() => activeTab = TabMode.manifest}
            >
                <div class="flex items-center gap-2">
                    <InfoCircleOutline size="md" />
                    <p>Manifest</p>
                </div>
            </button>
        </li>
    </ul>
</div>

<div>
    <div class={activeTab === TabMode.settings ? '' : 'hidden'} role="tabpanel">
        <Table2Cols bind:entry={settings}/>
    </div>
    <div class={activeTab === TabMode.manifest ? '' : 'hidden'} role="tabpanel">
        <Table2Cols bind:entry={manifest}/>
    </div>
</div>


