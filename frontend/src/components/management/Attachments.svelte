<script lang="ts">
    import Icon from "../Icon.svelte";
    import {
        ApiResponse,
        ContentType,
        get_attachment_url,
        query,
        QueryType,
        request,
        RequestType,
        ResourceAttachementType,
        ResourceType,
        upload_with_payload,
    } from "@/dmart";
    import {Level, showToast} from "@/utils/toast";
    import Media from "./Media.svelte";
    import {Button, Input, Label, Modal, ModalBody, ModalFooter, ModalHeader,} from "sveltestrap";
    import {JSONEditor, Mode} from "svelte-jsoneditor";
    import {jsonToFile} from "@/utils/jsonToFile";

    export let attachments: Array<any> = [];

    export let space_name: string;
    export let subpath: string;
    export let parent_shortname: string;

    // exp rt let forceRefresh;
    let shortname = "auto";
    let isModalInUpdateMode = false;
    let isModalInMetaUpdateMode = false;
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
    function handleView(attachmentShortname: string) {
        for (const attachmentGroup of attachments) {
            for (const attachment of attachmentGroup) {
                if (attachment.shortname === attachmentShortname) {
                    content = {
                        json: attachment,
                        text: undefined,
                    };
                }
            }
        }
        openViewAttachmentModal = true;
    }

    function getFileExtension(filename: string) {
        let ext = /^.+\.([^.]+)$/.exec(filename);
        return ext == null ? "" : ext[1];
    }

    async function handleDelete(item: {
        shortname: string;
        subpath: string;
        resource_type: ResourceType;
    }) {
        if (
            confirm(`Are you sure want to delete ${item.shortname} attachment`) === false
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
            location.reload();
        }
        else {
            showToast(Level.warn);
        }
    }

    let payloadFiles: FileList;

    let payloadContent: any = { json: {}, text: undefined  };
    let payloadData: string;
    let selectedSchema: string;
    let resourceType: ResourceAttachementType = ResourceAttachementType.media;
    let contentType: ContentType = ContentType.image;
    async function upload() {
        if (isModalInUpdateMode){
            if (trueResourceType !== null){
                resourceType = trueResourceType;
                trueResourceType = null;
            }
        }

        let response: ApiResponse;
        if (resourceType == ResourceAttachementType.comment) {
            const request_dict = {
                space_name,
                request_type: isModalInUpdateMode ? RequestType.update : RequestType.create,
                records: [
                    {
                        resource_type: ResourceType.comment,
                        shortname: shortname,
                        subpath: `${subpath}/${parent_shortname}`,
                        attributes: {
                            is_active: true,
                            state: "xxx",
                            body: payloadData,
                        },
                    },
                ],
            };
            response = await request(request_dict);
        }
        else if (
            [
                ContentType.image,
                ContentType.pdf,
                ContentType.audio,
                ContentType.video,
                ContentType.jsonl,
                ContentType.csv,
            ].includes(contentType)
        ) {
            response = await upload_with_payload(
                space_name,
                subpath + "/" + parent_shortname,
                ResourceType[resourceType],
                contentType,
                shortname,
                ResourceType[resourceType] === ResourceType.json
                    ? jsonToFile(payloadContent)
                    : payloadFiles[0]
            );
        }
        else if (
            [
                ContentType.json,
                ContentType.text,
                ContentType.html,
                ContentType,
            ].includes(contentType)
        ) {
            let _payloadContent = payloadContent.json
                ? structuredClone(payloadContent.json)
                : JSON.parse(payloadContent.text ?? '{}');
            const request_dict = {
                space_name,
                request_type: isModalInUpdateMode ? RequestType.update : RequestType.create,
                records: [
                    {
                        resource_type: ResourceType[resourceType],
                        shortname: shortname,
                        subpath: `${subpath}/${parent_shortname}`,
                        attributes: {
                            is_active: true,
                            payload: {
                                content_type: contentType,
                                schema_shortname:
                                    resourceType == ResourceAttachementType.json && selectedSchema
                                        ? selectedSchema
                                        : null,
                                body:
                                    resourceType == ResourceAttachementType.json
                                        ? _payloadContent
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
        }
        else {
            showToast(Level.warn);
        }

        isModalInMetaUpdateMode = false;
    }

    async function updateMeta(){
        if (isModalInUpdateMode){
            if (trueResourceType !== null){
                resourceType = trueResourceType;
                trueResourceType = null;
            }
        }

        let _payloadContent = payloadContent.json
            ? structuredClone(payloadContent.json)
            : JSON.parse(payloadContent.text ?? '{}');
        const request_dict = {
            space_name,
            request_type: RequestType.update,
            records: [
                {
                    resource_type: ResourceType[resourceType],
                    shortname: shortname,
                    subpath: `${subpath}/${parent_shortname}`,
                    attributes: {
                        is_active: true,
                        payload: {
                            content_type: contentType,
                            schema_shortname:selectedSchema,
                            body: _payloadContent,
                        },
                    },
                },
            ],
        };
        const response = await request(request_dict);
        if (response.status === "success") {
            showToast(Level.info);
            openCreateAttachemntModal = false;
            location.reload();
        }
        else {
            showToast(Level.warn);
        }
    }

    $: {
        switch (resourceType){
            case ResourceAttachementType.media: contentType = ContentType.image; break;
            case ResourceAttachementType.comment: contentType = ContentType.text; break;
            case ResourceAttachementType.json: contentType = ContentType.json; break;
        }
    }

    let trueResourceType = null;
    function handleMetaEditModal(attachment) {
        const _attachment = structuredClone(attachment);
        delete _attachment?.payload?.body;
        trueResourceType = _attachment.resource_type
        shortname = _attachment.shortname;
        resourceType = ResourceAttachementType.json;
        payloadContent = {json: _attachment}

        isModalInMetaUpdateMode = true;
        openCreateAttachemntModal = true;
        isModalInUpdateMode = true;
    }
    function handleContentEditModal(attachment) {
        const _attachment = structuredClone(attachment);
        shortname = _attachment.shortname;
        resourceType = _attachment.resource_type;

        if (attachment.resource_type === ResourceAttachementType.json){
            payloadContent = {json: _attachment.attributes.payload.body}
        }
        else if (attachment.resource_type === ResourceAttachementType.comment){
            payloadData = _attachment.attributes.body;
        }
        else {
            payloadContent = _attachment.attributes.payload.body;
        }

        openCreateAttachemntModal = true;
        isModalInUpdateMode = true;
    }
</script>

<Modal
        isOpen={openCreateAttachemntModal}
        toggle={toggleCreateAttachemntModal}
        size={"lg"}
>
  <ModalHeader toggle={toggleCreateAttachemntModal}>
    <h3>
      {isModalInUpdateMode ? "Update attachment" : "Add attachment"}
    </h3>
  </ModalHeader>
  <ModalBody>
    <div class="d-flex flex-column">
      <Label>Attachment shortname</Label>
      <Input accept="image/png, image/jpeg" bind:value={shortname} disabled={isModalInUpdateMode}/>
      <Label>Attachement Type</Label>
      <Input type="select" bind:value={resourceType} disabled={isModalInUpdateMode}>
        {#each Object.values(ResourceAttachementType).filter(type => type !== ResourceAttachementType.alteration && type !== ResourceAttachementType.relationship) as type}
          <option value={type}>{type}</option>
        {/each}
      </Input>
      {#key resourceType}
        {#if resourceType === ResourceAttachementType.media}
          <Label>Content Type</Label>
          <Input type="select" bind:value={contentType} disabled={isModalInUpdateMode}>
            {#each Object.values(ContentType).filter(type => type !== ContentType.json) as type}
              <option value={type}>{type}</option>
            {/each}
          </Input>
        {/if}
      {/key}
      <hr />
      {#key resourceType}
        {#if resourceType === ResourceAttachementType.media}
          {#if contentType === ContentType.jsonl}
            <Label>JSONL File</Label>
            <Input
                    bind:files={payloadFiles}
                    type="file"
                    accept=".jsonl" />
          {:else if contentType === ContentType.csv}
            <Label>CSV File</Label>
            <Input
                    bind:files={payloadFiles}
                    type="file"
                    accept=".csv" />
          {:else if contentType !== ContentType.text && contentType !== ContentType.html}
            <Label>Payload File</Label>
            <Input
                    accept="image/png, image/jpeg"
                    bind:files={payloadFiles}
                    type="file"
            />
          {:else}
            <Input type={"textarea"} bind:value={payloadData} />
          {/if}
        {:else if resourceType === ResourceAttachementType.json}
          <Label>Schema</Label>
          <Input class="mb-3" bind:value={selectedSchema} type="select" disabled={isModalInUpdateMode}>
            <option value={""}>{"None"}</option>
            {#await query({ space_name, type: QueryType.search, subpath: "/schema", search: "", retrieve_json_payload: true, limit: 99 }) then schemas}
              {#each schemas.records.map((e) => e.shortname) as schema}
                <option value={schema}>{schema}</option>
              {/each}
            {/await}
          </Input>
          <JSONEditor bind:content={payloadContent} />
        {:else if resourceType === ResourceAttachementType.comment}
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
    <Button type="button" color="primary" on:click={isModalInMetaUpdateMode ? updateMeta : upload}>
      {isModalInUpdateMode ? "Update" : "Upload"}
    </Button>
  </ModalFooter>
</Modal>

<Modal
        isOpen={openViewAttachmentModal}
        toggle={toggleViewAttachmentModal}
        size={"lg"}
>
  <ModalHeader />
  <ModalBody>
    <JSONEditor
            mode={Mode.text}
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
  <div on:click={() => {
    openCreateAttachemntModal = true;
    isModalInUpdateMode = false;
  }}>
    <Icon style="cursor: pointer;" name="plus-square" />
  </div>
</div>

<div class="d-flex justify-content-center flex-column px-5">
  {#each attachments.flat(1) as attachment}
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
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div
                  class="mx-1"
                  style="cursor: pointer;"
                  on:click={() => {
             handleMetaEditModal(attachment);
            }}
          ><Icon name="code-slash" /></div>
          {#if [
              ResourceType.json,
              ResourceType.content,
              ResourceType.comment,
          ].includes(attachment.resource_type)}
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <!-- svelte-ignore a11y-no-static-element-interactions -->
            <div
                    class="mx-1"
                    style="cursor: pointer;"
                    on:click={() => {
                handleContentEditModal(attachment);
              }}
            ><Icon name="pencil" /></div>
          {/if}
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
</div>
