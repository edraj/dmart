<script>
  import {
    Button,
    Modal,
    ModalBody,
    ModalFooter,
    ModalHeader,
  } from "sveltestrap";
  import Input from "./Input.svelte";
  import { _ } from "../../../i18n/index.js";
  import {
    dmartQuery,
    dmartListSchemas,
    dmartContent,
    dmartPostMedia,
  } from "../dmart";
  // import sha1 from "../sha1";
  import { entries } from "../_stores/entries.js";
  import { getNotificationsContext } from "svelte-notifications";
  import { createEventDispatcher } from "svelte";
  const dispatch = createEventDispatcher();

  let schemas = [];

  dmartListSchemas().then((resp) => {
    schemas = resp.records.map((r) => ({
      shortname: r.shortname,
      payload: r.attributes.payload,
    }));
    schemaShortname = schemas?.[0].shortname;
  });

  const { addNotification } = getNotificationsContext();

  export let open = false;
  export let size = undefined;
  export let subpath = null;
  export let data = null;
  export let parent_shortname = undefined;
  export let fixResourceType = undefined;

  let shortname;
  let displayname;
  let resource_type;
  let schemaShortname;
  let payload = "";
  let payload_type = "json";
  let tags;
  let description;
  let displayedSubpath;
  let mediafile;

  if (fixResourceType) resource_type = fixResourceType;
  else resource_type = "content";

  if (data) {
    subpath = data.subpath;
    shortname = data.shortname;
    displayname = data.displayname;
    description = data.attributes.description;
    resource_type = data.resource_type;
    if (
      "attributes" in data &&
      "embedded" in data.attributes &&
      data.attributes.payload.embedded
    )
      payload = data.attributes.payload.embedded;
    if ("attributes" in data && "tags" in data.attributes)
      tags = data.attributes.tags.join(",");
  } else {
    displayname = description = tags = "";
  }

  displayedSubpath = subpath;
  if (parent_shortname) displayedSubpath = `${subpath}/${parent_shortname}`;

  async function handle() {
    let record = {
      resource_type: resource_type,
      subpath: subpath,
      shortname: shortname,
      attributes: {
        displayname: displayname,
        description: description,
        tags: tags.split(/[,،]+/),
      },
    };

    if (parent_shortname) record.parent_shortname = parent_shortname;

    if (data == null) {
      // We are handling entry creation here.
      if (enableUpload && mediafile) {
        console.log("My sha1: ", mediafile.sha1);
        record.attributes.payload = {
          checksum: `sha1:${mediafile.sha1}`,
          filepath: mediafile.name,
          content_type: mediafile.type,

          bytesize: mediafile.size,
        };
      }
    }

    let resp;
    let op;

    if (data) {
      // Fix subpath if the type is folder.
      if (resource_type == "folder" && subpath.endsWith(shortname)) {
        record.subpath = subpath.substring(0, subpath.lastIndexOf("/"));
        console.log(`Fixing subpath: from ${subpath} to ${record.subpath}`);
      }
      resp = await dmartContent("update", record);
      op = "updated";
    } else {
      if (resource_type == "media") {
        if (mediafile) {
          console.log("My sha1: ", mediafile.sha1);
          record.attributes.payload = {
            checksum: `sha1:${mediafile.sha1}`,
            filepath: mediafile.name,
            content_type: mediafile.type,
            bytesize: mediafile.size,
          };
          resp = await dmartPostMedia(record, mediafile);
        } else {
          alert("Media file must be selected");
          resp = { status: "failed" };
        }
      } else {
        record.attributes.payload = {
          // checksum: `sha1:${sha1(payload)}`,
          body: JSON.parse(payload),
          schema_shortname: schemaShortname,
          content_type: payload_type,
          bytesize: new Blob([payload]).size,
        };
        resp = await dmartContent("create", record);
      }
      op = "created";
    }

    if (resp.status == "success") {
      if (!parent_shortname) {
        // If this is not attachment, add it as main entry.
        let entry = {
          data: (
            await dmartQuery({
              type: "subpath",
              subpath: record.subpath,
              filter_shortnames: [record.shortname],
            })
          ).records?.[0],
        };

        // entry.data.subpath = subpath;
        if (!entry.data.attachments)
          entry.data.attachments = { media: [], reply: [], reaction: [] };
        entry.data.displayname = record.attributes.displayname;
        entries.add(entry.data.subpath, entry);
      }

      addNotification({
        text: `${op} "${shortname}" under ${subpath}`,
        position: "bottom-center",
        type: resp.status == "success" ? "success" : "warning",
        removeAfter: 5000,
      });

      dispatch(op, record);
      //console.log("Content modal: ", record, resp);
      //console.log("Content modal result: ", resp.results[0]);
      //console.log($entries[subpath]);

      open = false;
    }
  }

  function toggle() {
    open = !open;
  }

  let enableUpload = "media" == resource_type;
  function resourceTypeChanged(event) {
    console.log(event.target.value);
    enableUpload = "media" == event.target.value;
  }

  function uploadMedia(event) {
    mediafile = event.target.files[0];
    console.log("Name: ", mediafile.name, "Size: ", mediafile.size);
    var reader = new FileReader();
    reader.onload = function (event) {
      // mediafile["sha1"] = sha1(event.target.result);
      // console.log("Completed reading file: ", mediafile.sha1);
    };
    reader.readAsArrayBuffer(mediafile);
  }
</script>

<Modal isOpen={open} {toggle} size={"lg"}>
  <ModalHeader>
    {#if data}
      {$_("edit")}
    {:else}
      {$_("create")}
    {/if}
    {$_(resource_type)}
  </ModalHeader>
  <ModalBody>
    <Input
      id="subpath"
      title={$_("subpath")}
      value={displayedSubpath}
      readonly={true}
      type="text"
    />
    <Input
      id="shortname"
      title={$_("shortname")}
      bind:value={shortname}
      type="text"
    />
    <Input
      id="displayname"
      title={$_("displayname")}
      bind:value={displayname}
      type="text"
    />
    <Input id="tags" title={$_("tags")} bind:value={tags} type="text" />
    <Input
      id="description"
      type="textarea"
      title={$_("description")}
      bind:value={description}
    />

    {#if fixResourceType || data}
      <Input
        id="resource_type"
        title={$_("resource_type")}
        value={resource_type}
        readonly={true}
        type="text"
      />
    {:else}
      <Input
        id="resource_type"
        type="select"
        title={$_("resource_type")}
        bind:value={resource_type}
        on:change={resourceTypeChanged}
      >
        <option value="folder">{$_("folder")}</option>
        <option value="content">{$_("content")}</option>
      </Input>
    {/if}

    {#if !data && resource_type != "folder"}
      {#if enableUpload}
        <Input
          id="upload"
          title={$_("upload")}
          type="file"
          on:change={uploadMedia}
        />
      {:else}
        <Input
          id="payload"
          type="textarea"
          title={$_("payload")}
          bind:value={payload}
        />
        <Input
          id="payload_type"
          title={$_("payload_type")}
          bind:value={payload_type}
          type="select"
        >
          <option value="markdown">{$_("text_markdown")}</option>
          <option value="json">{$_("text_json")}</option>
        </Input>

        <Input
          id="schemaShortname"
          type="select"
          title={$_("schame_shortname")}
          bind:value={schemaShortname}
        >
          {#each schemas as schema}
            <option value={schema.shortname}>{schema.shortname}</option>
          {/each}
        </Input>
      {/if}
    {/if}
  </ModalBody>
  <ModalFooter>
    <Button color="secondary" on:click={() => (open = false)}
      >{$_("cancel")}</Button
    >
    <Button color="primary" on:click={handle}>{$_("accept")}</Button>
  </ModalFooter>
</Modal>
