<script lang="ts">
  import Table from "@/components/management/Table.svelte";
  import { _ } from "@/i18n";
  import { TabPane, TabContent } from "sveltestrap";
  import { Col } from "sveltestrap";
  import Prism from "@/components/Prism.svelte";
  import QueryFormH from "@/components/management/QueryFormH.svelte";

  let results = { records: [] };
  let rows = [];

  function handleResponse(event: CustomEvent) {
    results = event.detail;
    rows = results.records;
  }

  let cols = {
    shortname: {
      path: "shortname",
      title: $_("shortname"),
      type: "string",
    },
    displayname: {
      path: "attributes.displayname.en",
      title: $_("displayname"),
      type: "string",
    },
    tags: {
      path: "attributes.tags",
      title: $_("tags"),
      type: "string",
    },
    payload: {
      path: "attributes.payload.schema_shortname",
      title: $_("schema_shortname"),
      type: "string",
    },
    is_active: {
      path: "attributes.is_active",
      title: $_("is_active"),
      type: "string",
    },
  };
</script>

<Col class="h-100  px-2 mt-2">
  <QueryFormH on:response={handleResponse} />
  <div class="flex-grow-0 overflow-y-auto mt-1" style="min-height: 0;">
    <TabContent class="h-100">
      <TabPane class="h-100" tabId="original" tab={$_("raw")} active>
        <Prism bind:code={results} />
      </TabPane>
      <TabPane class="h-100" tabId="tabular" tab={$_("tabular")}>
        <Table bind:cols bind:rows />
      </TabPane>
    </TabContent>
  </div>
</Col>
