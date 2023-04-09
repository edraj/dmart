<script>
  import { params } from "@roxi/routify";
  import { createAjvValidator } from "svelte-jsoneditor";
  import ContentEditSection from "../../../../_components/ContentEditSection.svelte";
  import {
    dmartEntry,
    dmartGetSchemas,
    dmartRequest,
  } from "../../../../../../dmart.js";
  import { toastPushFail, toastPushSuccess } from "../../../../../../utils";

  let height;

  let space_name;
  let subpath;
  let resource_type = "content";
  let schema_name;
  let shortname;

  let metaContent = {
    json: {},
    text: undefined,
  };
  let bodyContent = {
    json: {},
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
    shortname = $params.shortname;

    const meta = await dmartEntry(
      resource_type,
      space_name,
      subpath,
      shortname,
      "",
      "json",
      "json",
      "entry"
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

      const body = await dmartEntry(
        resource_type,
        space_name,
        subpath,
        shortname,
        ""
      );
      bodyContent.json = body;
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

    if (Object.keys(bodyContent.json).length) {
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
{:catch error}
  <p style="color: red">{error.message}</p>
{/await}
