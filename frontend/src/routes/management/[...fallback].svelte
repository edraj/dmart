<script>
  import { Circle2 } from "svelte-loading-spinners";
  import { dmartEntry, dmartRequest } from "../../dmart";
  import { toastPushFail, toastPushSuccess } from "../../utils";
  import ContentEditSection from "./_components/ContentEditSection.svelte";

  let space_name;
  let shortname;
  let subpath;
  let records = [{}];
  let bodyContent;
  let metaContent;
  let metaContentAttachement;
  let historyQuery;
  let showContentEditSection = false;
  let currentItem = 0;
  let height;

  async function handleSave() {
    const metaData = metaContent.json
      ? { ...metaContent.json }
      : JSON.parse(metaContent.text);
    const data = { ...metaData };
    data.attributes.payload.body =
      bodyContent.json ??
      JSON.parse(bodyContent.text) ??
      data.attributes.payload.body;
    const response = await dmartRequest("managed/request", {
      space_name,
      request_type: "update",
      records: [data],
    });
    if (response.status === "success") {
      toastPushSuccess();
      records[currentItem - 1] = metaData;
    } else {
      toastPushFail();
    }
  }

  async function handleUpdateUpdate() {
    let url = location.pathname;
    if (url.startsWith("/management")) {
      url = url.replace("/management/", "").split("/");
      space_name = url[0];
      subpath = "/" + url.slice(1, url.length - 1).join("/");
      shortname = url[url.length - 1];

      console.log({ space_name }, { subpath }, { shortname });

      if (space_name && shortname && subpath) {
        const request = {
          type: "subpath",
          space_name,
          subpath,
          branch_name: "master",
          filter_schema_names: ["meta"],
          filter_shortnames: [shortname],
          retrieve_json_payload: true,
          retrieve_attachments: true,
        };
        const response = await dmartRequest("managed/query", request);
        console.log({ response });
        if (response.status === "success") {
          toastPushSuccess();
          records[0] = response.records[0];
          showContentEditSection = true;
          const record = records[0];

          const json = { ...record };
          metaContentAttachement = json.attachments;

          delete json.attachments;
          metaContent = {
            json,
            text: undefined,
          };

          if (record?.attributes?.payload?.body) {
            bodyContent = {
              json: await dmartEntry(
                record.resource_type,
                space_name,
                record.subpath,
                shortname,
                "meta",
                "json"
              ),
              text: undefined,
            };
          }

          historyQuery = {
            type: "history",
            space_name: space_name,
            filter_shortnames: [shortname],
            subpath: record.subpath,
            retrieve_json_payload: true,
          };
        } else {
          toastPushFail();
        }
      }
    }
  }

  let init = handleUpdateUpdate();
</script>

<svelte:window bind:innerHeight={height} />

{#await init}
  <Circle2 size="200" color="#FF3E00" unit="px" duration="1s" />
{:then _}
  {#if showContentEditSection}
    <ContentEditSection
      bind:space_name
      bind:subpath
      bind:shortname
      bind:records
      bind:bodyContent
      bind:metaContent
      bind:metaContentAttachement
      bind:historyQuery
      bind:showContentEditSection
      {handleSave}
      bind:currentItem
      bind:height
    />
  {/if}
{:catch error}
  <p style="color: red">{error.message}</p>
{/await}
