<script>
  import { params } from "@roxi/routify";
  import { createAjvValidator } from "svelte-jsoneditor";
  import ContentEditSection from "../../../../../../_components/ContentEditSection.svelte";
  import {
    dmartEntry,
    dmartGetSchemas,
    dmartRequest,
  } from "../../../../../../../../dmart.js";
  import {
    toastPushFail,
    toastPushSuccess,
  } from "../../../../../../../../utils";
  import ContentApiSection from "../../../../../../_components/ContentAPISection.svelte";

  let height;

  let space_name;
  let subpath;
  let resource_type;
  let schema_name;
  let shortname;

  let metaContent = {
    json: {},
    text: undefined,
  };
  let bodyContent = {
    json: null,
    text: undefined,
  };
  let metaContentAttachement = [];
  let historyQuery;
  let errorContent = {
    json: {},
    text: undefined,
  };
  let isSchemaValidated = true;
  let validator = createAjvValidator({ schema: {} });
  let isError = false;

  function cleanUpSchema(obj) {
    for (let prop in obj) {
      if (prop === "comment") delete obj[prop];
      else if (typeof obj[prop] === "object") cleanUpSchema(obj[prop]);
    }
  }

  async function initPage() {
    space_name = $params.space_name;
    subpath = $params.subpath.replaceAll("-", "/");
    resource_type = $params.resource_type;
    schema_name = $params.schema_name;
    shortname = $params.shortname;

    const meta = await dmartEntry(
      resource_type,
      space_name,
      subpath,
      shortname,
      "",
      "json",
      "json",
      "entry",
      true
    );
    metaContent.json = meta;

    historyQuery = {
      type: "history",
      space_name: space_name,
      filter_shortnames: [shortname],
      subpath: subpath,
      retrieve_json_payload: true,
    };
    metaContentAttachement = meta.attachments;
    if (meta.payload?.schema_shortname) {
      await dmartGetSchemas(space_name, meta.payload.schema_shortname)
        .then((json) => {
          const schema = json.records[0].attributes["payload"].body;
          cleanUpSchema(schema.properties);
          validator = createAjvValidator({ schema });
        })
        .catch((e) => {
          console.log(e);
        });

      if (meta?.payload?.content_type === "json") {
        const body = await dmartEntry(
          resource_type,
          space_name,
          subpath,
          shortname,
          schema_name
        );
        bodyContent.json = body;
      }
    }
  }
  let init = initPage();

  const handleSave = async () => {
    if (!isSchemaValidated) {
      alert("The content does is not validated agains the schema");
      return;
    }
    isError = false;

    const metaData = metaContent.json
      ? { ...metaContent.json }
      : JSON.parse(metaContent.text);
    const data = { ...metaData };
    if (bodyContent.json !== null) {
      data.payload.body =
        bodyContent.json ?? JSON.parse(bodyContent.text) ?? data.payload.body;
    }

    const response = await dmartRequest("managed/request", {
      space_name: space_name,
      request_type: "update",
      records: [
        {
          resource_type,
          shortname,
          subpath,
          attributes: data,
        },
      ],
    });
    if (response.status === "success") {
      toastPushSuccess();
    } else {
      toastPushFail();
      errorContent.json = response.error;
      isError = true;
    }
  };
</script>

<svelte:window bind:innerHeight={height} />

{#await init}
  ...
{:then _}
  {#if schema_name === "api"}
    <ContentApiSection
      request={{
        end_point: bodyContent.json.end_point,
        verb: bodyContent.json.verb,
      }}
      input={bodyContent.json.request_body}
    />
  {/if}
  {#if schema_name !== "api"}
    <ContentEditSection
      bind:space_name={$params.space_name}
      bind:subpath={$params.subpath}
      bind:bodyContent
      bind:metaContent
      bind:errorContent
      bind:validator
      bind:isSchemaValidated
      bind:isError
      bind:metaContentAttachement
      bind:historyQuery
      {handleSave}
      bind:shortname
      bind:height
    />
  {/if}
{:catch error}
  <p style="color: red">{error.message}</p>
{/await}
