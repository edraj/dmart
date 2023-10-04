<script lang="ts">
  import Icon from "../Icon.svelte";
  import {
    upload_with_payload,
    request,
    get_attachment_url,
    query,
    QueryType,
    RequestType,
    ContentType,
    ResourceType,
    ResourceAttachementType,
    ApiResponse,
  } from "@/dmart";
  import { showToast, Level } from "@/utils/toast";
  import Media from "./Media.svelte";
  import {
    Button,
    Input,
    Label,
    Modal,
    ModalBody,
    ModalFooter,
    ModalHeader,
  } from "sveltestrap";
  import { JSONEditor, JSONContent, Mode } from "svelte-jsoneditor";

  export let attachments: Array<any>;
  export let space_name: string;
  export let subpath: string;
  export let parent_shortname: string;

  // exp rt let forceRefresh;
  let shortname = "auto";

  let openViewAttachmentModal = false;
  function toggleViewAttachmentModal() {
    openViewAttachmentModal = !openViewAttachmentModal;
  }

  let openCreateAttachemntModal = false;
  function toggleCreateAttachemntModal() {
    openCreateAttachemntModal = !openCreateAttachemntModal;
  }

  let content = {
    json: {},
    text: undefined,
  };
  function handleView(attachemntTitle: string) {
    content = {
      json: attachments.filter((e) => e.shortname === attachemntTitle)[0],
      text: undefined,
    };
    openViewAttachmentModal = true;
  }

  function getFileExtension(filename: string) {
    var ext = /^.+\.([^.]+)$/.exec(filename);
    return ext == null ? "" : ext[1];
  }

  async function handleDelete(item: {
    shortname: string;
    subpath: string;
    resource_type: ResourceType;
  }) {
    if (
      confirm(`Are you sure want to delete ${item.shortname} attachment`) ===
      false
    ) {
      return;
    }

    const request_dict = {
      space_name,
      request_type: RequestType.delete,
      records: [
        {
          resource_type: item.resource_type,
          shortname: item.shortname,
          subpath: `${item.subpath}/${parent_shortname}`,
          attributes: {},
        },
      ],
    };
    const response = await request(request_dict);
    if (response.status === "success") {
      showToast(Level.info);
      attachments = attachments.filter(
        (e: { shortname: string }) => e.shortname !== item.shortname
      );
      openCreateAttachemntModal = false;
    } else {
      showToast(Level.warn);
    }
  }

  let payloadFiles: FileList;

  let payloadContent: JSONContent = { json: { name: "test" } };
  let payloadData: string;
  let selectedSchema: string;
  let resourceType: ResourceAttachementType = ResourceAttachementType.media;
  let contentType: ContentType = ContentType.image;
  async function upload() {
    let response: ApiResponse;

    if (resourceType == ResourceAttachementType.comment) {
      const request_dict = {
        space_name,
        request_type: RequestType.create,
        records: [
          {
            resource_type: ResourceType.comment,
            shortname: shortname,
            subpath: `${subpath}/${parent_shortname}`,
            attributes: {
              state: "xxx",
              body: payloadData,
            },
          },
        ],
      };
      response = await request(request_dict);
    } else if (
      [
        ContentType.image,
        ContentType.pdf,
        ContentType.audio,
        ContentType.video,
      ].includes(contentType)
    ) {
      response = await upload_with_payload(
        space_name,
        subpath + "/" + parent_shortname,
        ResourceType[resourceType],
        shortname,
        payloadFiles[0]
      );
    } else if (
      [
        ContentType.json,
        ContentType.text,
        ContentType.html,
        ContentType,
      ].includes(contentType)
    ) {
      const request_dict = {
        space_name,
        request_type: RequestType.create,
        records: [
          {
            resource_type: ResourceType[resourceType],
            shortname: shortname,
            subpath: `${subpath}/${parent_shortname}`,
            attributes: {
              payload: {
                content_type: contentType,
                schema_shortname:
                  resourceType == ResourceAttachementType.json && selectedSchema
                    ? selectedSchema
                    : null,
                body:
                  resourceType == ResourceAttachementType.json
                    ? payloadContent.json
                    : payloadData,
              },
            },
          },
        ],
      };
      response = await request(request_dict);
    }

    if (response.status === "success") {
      showToast(Level.info);
      openCreateAttachemntModal = false;
      location.reload();
    } else {
      showToast(Level.warn);
    }
  }
</script>

<Modal
  isOpen={openCreateAttachemntModal}
  toggle={toggleCreateAttachemntModal}
  size={"lg"}
>
  <ModalHeader toggle={() => (openCreateAttachemntModal = false)}>
    <h3>Add attachment</h3>
  </ModalHeader>
  <ModalBody>
    <div class="d-flex flex-column">
      <Label>Attachment shortname</Label>
      <Input accept="image/png, image/jpeg" bind:value={shortname} />
      <Label>Attachement Type</Label>
      <Input type="select" bind:value={resourceType}>
        {#each Object.values(ResourceAttachementType) as type}
          {#if type != ResourceAttachementType.alteration && type != ResourceAttachementType.relationship}
            <option value={type}>{type}</option>
          {/if}
        {/each}
      </Input>
      {#key resourceType}
        {#if resourceType == ResourceAttachementType.media}
          <Label>Content Type</Label>
          <Input type="select" bind:value={contentType}>
            {#each Object.values(ContentType) as type}
              {#if type != ContentType.json}
                <option value={type}>{type}</option>
              {/if}
            {/each}
          </Input>
        {/if}
      {/key}
      <hr />
      {#key resourceType}
        {#if resourceType == ResourceAttachementType.media}
          {#if contentType != ContentType.text && contentType != ContentType.html}
            <Label>Payload File</Label>
            <Input
              accept="image/png, image/jpeg"
              bind:files={payloadFiles}
              type="file"
            />
          {:else}
            <Input type={"textarea"} bind:value={payloadData} />
          {/if}
        {:else if resourceType == ResourceAttachementType.json}
          <Input bind:value={selectedSchema} type="select">
            <option value={""}>{"None"}</option>
            {#await query( { space_name, type: QueryType.search, subpath: "/schema", search: "", retrieve_json_payload: true, limit: 99 } ) then schemas}
              {#each schemas.records.map((e) => e.shortname) as schema}
                <option value={schema}>{schema}</option>
              {/each}
            {/await}
          </Input>
          <br />

          <JSONEditor mode={Mode.text} bind:content={payloadContent} />
        {:else if resourceType == ResourceAttachementType.comment}
          <Input type={"textarea"} bind:value={payloadData} />
        {:else}
          <b> TBD ... show custom fields for resource type : {resourceType} </b>
        {/if}
      {/key}
    </div>
  </ModalBody>
  <ModalFooter>
    <Button
      type="button"
      color="secondary"
      on:click={() => (openCreateAttachemntModal = false)}>close</Button
    >
    <Button type="button" color="primary" on:click={upload}>Upload</Button>
  </ModalFooter>
</Modal>

<Modal
  isOpen={openViewAttachmentModal}
  toggle={toggleViewAttachmentModal}
  size={"lg"}
>
  <ModalHeader />
  <ModalBody>
    <JSONEditor mode={Mode.text}
      content={{ json: JSON.parse(JSON.stringify(content)) }}
      readOnly={true}
    />
  </ModalBody>
  <ModalFooter>
    <Button
      type="button"
      color="secondary"
      on:click={() => (openViewAttachmentModal = false)}>close</Button
    >
  </ModalFooter>
</Modal>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="d-flex justify-content-end mx-2 flex-row">
  <div on:click={() => (openCreateAttachemntModal = true)}>
    <Icon style="cursor: pointer;" name="plus-square" />
  </div>
</div>

<div class="d-flex justify-content-center flex-column px-5">
  {#if attachments}
    {#each attachments as attachment}
      <hr />
      <div class="col">
        <div class="row mb-2">
          <a
            class="col-11"
            style="font-size: 1.25em;"
            href={get_attachment_url(
              attachment.resource_type,
              space_name,
              subpath,
              parent_shortname,
              attachment.shortname,
              getFileExtension(attachment.attributes?.payload?.body)
            )}
          >
            {attachment.shortname}</a
          >
          <div class="col-1 d-flex justify-content-between">
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <!-- svelte-ignore a11y-no-static-element-interactions -->
            <div
              class="mx-1"
              style="cursor: pointer;"
              on:click={async () => await handleDelete(attachment)}
            >
              <Icon name="trash" color="red" />
            </div>
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <!-- svelte-ignore a11y-no-static-element-interactions -->
            <div
              class="mx-1"
              style="cursor: pointer;"
              on:click={() => {
                handleView(attachment.shortname);
              }}
            >
              <Icon name="eyeglasses" color="grey" />
            </div>
          </div>
        </div>
        <div class="d-flex col justify-content-center">
          <Media
            resource_type={attachment.resource_type}
            attributes={attachment.attributes}
            displayname={attachment.shortname}
            url={get_attachment_url(
              attachment.resource_type,
              space_name,
              subpath,
              parent_shortname,
              attachment.shortname,
              getFileExtension(attachment.attributes?.payload?.body)
            )}
          />
        </div>
      </div>
      <hr />
    {/each}
  {/if}
</div>
