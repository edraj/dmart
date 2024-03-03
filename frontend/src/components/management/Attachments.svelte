<script lang="ts">
  import Icon from "../Icon.svelte";
  import {
    ApiResponse,
    ContentType,
    ContentTypeMedia,
    fetchDataAsset,
    get_attachment_content,
    get_attachment_url,
    query,
    QueryType,
    request,
    RequestType,
    ResourceAttachmentType,
    ResourceType,
    upload_with_payload,
  } from "@/dmart";
  import {Level, showToast} from "@/utils/toast";
  import Media from "./Media.svelte";
  import {Button, Col, Input, Label, Modal, ModalBody, ModalFooter, ModalHeader,} from "sveltestrap";
  import {JSONEditor, Mode} from "svelte-jsoneditor";
  import {jsonToFile} from "@/utils/jsonToFile";
  import Prism from "@/components/Prism.svelte";
  import {parseCSV, parseJSONL} from "@/utils/attachements";
  import {AxiosError} from "axios";
  import MarkdownEditor from "@/components/management/editors/MarkdownEditor.svelte";

  export let attachments: Array<any> = [];
  export let resource_type: string;
  export let space_name: string;
  export let subpath: string;
  export let parent_shortname: string;

  async function fetchDataAssetsForAttachments() {
    for (const attachment of attachments.flat(1)) {
      if (["csv", "parquet", "jsonl"].includes(attachment.resource_type)) {
        const r = await fetchDataAsset(
          resource_type,
          attachment.resource_type,
          space_name,
          subpath,
          parent_shortname,
          `SELECT * FROM '${attachment.shortname}'`
        );
        if (!(r instanceof AxiosError)) {
          attachment.dataAsset = r;
        } else {
            attachment.dataAsset = {
                code: r.response.data?.error?.code,
                message: r.response.data?.error?.message
            };
        }
      } else if (attachment.resource_type === "sqlite") {
        const tables = await fetchDataAsset(
          resource_type,
          attachment.resource_type,
          space_name,
          subpath,
          parent_shortname,
          "SELECT * FROM temp.information_schema.tables",
          [attachment.shortname]
        );
        attachment.dataAsset = (
          await Promise.all(
            tables.map(async (table) => {
              const r = await fetchDataAsset(
                resource_type,
                attachment.resource_type,
                space_name,
                subpath,
                parent_shortname,
                `SELECT * FROM '${table.table_name}' LIMIT 10`,
                [attachment.shortname]
              );
              return r instanceof AxiosError
                ? null
                : { table_name: table.table_name, rows: r };
            })
          )
        ).filter((item) => item !== null);
      }
    }
  }

  // exp rt let forceRefresh;
  let shortname = "auto";
  let isModalInUpdateMode = false;
  let openViewAttachmentModal = false;
  let openMetaEditAttachmentModal = false;

  function toggleViewAttachmentModal() {
    openViewAttachmentModal = !openViewAttachmentModal;
  }

  function toggleMetaEditAttachmentModal() {
    openMetaEditAttachmentModal = !openMetaEditAttachmentModal;
  }

  let openCreateAttachemntModal = false;

  function toggleCreateAttachemntModal() {
    openCreateAttachemntModal = !openCreateAttachemntModal;
  }

  let content = {
    json: {},
    text: undefined,
  };

  function handleView(attachment) {
    content = {
      json: attachment,
      text: undefined,
    };
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
      location.reload();
    } else {
      showToast(Level.warn);
    }
  }

  let payloadFiles: FileList;

  let payloadContent: any = { json: {}, text: undefined };
  let payloadData: string;
  let selectedSchema: string;
  let resourceType: ResourceAttachmentType = ResourceAttachmentType.media;
  let contentType: ContentType = ContentType.image;

  async function upload() {
    let response: ApiResponse;
    if (resourceType == ResourceAttachmentType.comment) {
      const request_dict = {
        space_name,
        request_type: isModalInUpdateMode
          ? RequestType.update
          : RequestType.create,
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
    } else if (
      [
        ResourceAttachmentType.csv,
        ResourceAttachmentType.jsonl,
        ResourceAttachmentType.sqlite,
        ResourceAttachmentType.parquet,
      ].includes(resourceType)
    ) {
      response = await upload_with_payload(
        space_name,
        subpath + "/" + parent_shortname,
        ResourceType[resourceType],
        ContentType[resourceType],
        shortname,
        ResourceType[resourceType] === ResourceType.json
          ? jsonToFile(payloadContent)
          : payloadFiles[0],
        resourceType === ResourceAttachmentType.csv ? selectedSchema : null
      );
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
        contentType,
        shortname,
        ResourceType[resourceType] === ResourceType.json
          ? jsonToFile(payloadContent)
          : payloadFiles[0]
      );
    } else if (
      [
        ContentType.json,
        ContentType.text,
        ContentType.html,
        ContentType.markdown,
        ContentType,
      ].includes(contentType)
    ) {
      let _payloadContent = payloadContent.json
        ? structuredClone(payloadContent.json)
        : JSON.parse(payloadContent.text ?? "{}");
      let request_dict = {
        space_name,
        request_type: isModalInUpdateMode
            ? RequestType.update
            : RequestType.create,
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
                              resourceType == ResourceAttachmentType.json && selectedSchema
                                  ? selectedSchema
                                  : null,
                          body:
                              resourceType == ResourceAttachmentType.json
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
    } else {
      showToast(Level.warn);
    }
  }

  let trueResourceType = null;
  let trueContentType = null;

  async function updateMeta() {
    if (isModalInUpdateMode) {
      if (trueResourceType !== null) {
        resourceType = trueResourceType;
        trueResourceType = null;
      }
      if (trueContentType !== null) {
        contentType = trueContentType;
        trueContentType = null;
      }
    }

    let _payloadContent = payloadContent.json
      ? structuredClone(payloadContent.json)
      : JSON.parse(payloadContent.text ?? "{}");

    _payloadContent.subpath = `${subpath}/${parent_shortname}`;
    const request_dict = {
      space_name,
      request_type: RequestType.update,
      records: [_payloadContent],
    };
    const response = await request(request_dict);
    if (response.status === "success") {
      showToast(Level.info);
      openCreateAttachemntModal = false;
      location.reload();
    } else {
      showToast(Level.warn);
    }
  }

  $: {
    switch (resourceType) {
      case ResourceAttachmentType.media:
        contentType = ContentType.image;
        break;
      case ResourceAttachmentType.comment:
        contentType = ContentType.text;
        break;
      case ResourceAttachmentType.json:
        contentType = ContentType.json;
        break;
    }
  }

  function handleMetaEditModal(attachment) {
    const _attachment = structuredClone(attachment);
    trueResourceType = ResourceAttachmentType[_attachment.resource_type];
    trueContentType = ContentType[_attachment?.payload?.content_type];
    delete _attachment?.payload?.body;
    shortname = _attachment.shortname;
    resourceType = ResourceAttachmentType.json;
    payloadContent = { json: _attachment, text: undefined };

    openMetaEditAttachmentModal = true;
    isModalInUpdateMode = true;
  }

  function handleContentEditModal(attachment) {
    const _attachment = structuredClone(attachment);
    shortname = _attachment.shortname;

    resourceType = _attachment.resource_type;
    contentType = _attachment?.attributes.payload?.content_type;
    if (attachment.resource_type === ResourceAttachmentType.json) {
      payloadContent = { json: _attachment.attributes.payload.body };
    } else if (attachment.resource_type === ResourceAttachmentType.comment) {
      payloadData = _attachment.attributes.body;
    } else {
      payloadData = _attachment.attributes.payload.body;
    }

    openCreateAttachemntModal = true;
    isModalInUpdateMode = true;
  }

  function handleRenderMenu(items: any, _context: any) {
    items = items.filter(
      (item) => !["tree", "text", "table"].includes(item.text)
    );
    const separator = {
      separator: true,
    };

    const itemsWithoutSpace = items.slice(0, items.length - 2);
    return itemsWithoutSpace.concat([
      separator,
      {
        space: true,
      },
    ]);
  }

  function setSchemaItems(schemas): Array<string> {
    if (schemas === null) {
      return [];
    }
    const _schemas = schemas.records.map((e) => e.shortname);
    return _schemas.filter(
      (e) => !["meta_schema", "folder_rendering"].includes(e)
    );
  }
</script>

<Modal
  isOpen={openMetaEditAttachmentModal}
  toggle={toggleMetaEditAttachmentModal}
  size={"lg"}
>
  <ModalHeader />
  <ModalBody>
    <JSONEditor
      onRenderMenu={handleRenderMenu}
      mode={Mode.text}
      bind:content={payloadContent}
    />
  </ModalBody>
  <ModalFooter>
    <Button type="button" color="primary" on:click={updateMeta}>Update</Button>
    <Button
      type="button"
      color="secondary"
      on:click={() => (openMetaEditAttachmentModal = false)}
    >
      close
    </Button>
  </ModalFooter>
</Modal>

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
      <Input
        accept="image/png, image/jpeg"
        bind:value={shortname}
        disabled={isModalInUpdateMode}
      />
      <Label>Attachment Type</Label>
      <Input
        type="select"
        bind:value={resourceType}
        disabled={isModalInUpdateMode}
      >
        {#each Object.values(ResourceAttachmentType).filter((type) => type !== ResourceAttachmentType.alteration) as type}
          <option value={type}>{type}</option>
        {/each}
      </Input>
      {#key resourceType}
        {#if resourceType === ResourceAttachmentType.media}
          <Label>Content Type</Label>
          <Input
            type="select"
            bind:value={contentType}
            disabled={isModalInUpdateMode}
          >
            {#each Object.values(ContentTypeMedia) as type}
              <option value={type}>{type}</option>
            {/each}
          </Input>
        {/if}
      {/key}
      <hr />
      {#key resourceType}
        {#if resourceType === ResourceAttachmentType.media}
          {#if contentType === ContentType.image}
            <Label>Image File</Label>
            <Input
              accept="image/png, image/jpeg"
              bind:files={payloadFiles}
              type="file"
            />
          {:else if contentType === ContentType.pdf}
            <Label>PDF File</Label>
            <Input
              accept="application/pdf"
              bind:files={payloadFiles}
              type="file"
            />
          {:else if contentType === ContentType.audio}
            <Label>Audio File</Label>
            <Input accept="audio/*" bind:files={payloadFiles} type="file" />
          {:else if contentType === ContentType.python}
            <Label>Python File</Label>
            <Input accept=".py" bind:files={payloadFiles} type="file" />
          {:else if contentType === ContentType.markdown}
            <MarkdownEditor bind:content={payloadData} />
          {:else}
            <Input type={"textarea"} bind:value={payloadData} />
          {/if}
        {:else if resourceType === ResourceAttachmentType.json}
          <Label>Schema</Label>
          <Input
            class="mb-3"
            bind:value={selectedSchema}
            type="select"
            disabled={isModalInUpdateMode}
          >
            <option value={""}>{"None"}</option>
            {#await query( { space_name, type: QueryType.search, subpath: "/schema", search: "", retrieve_json_payload: true, limit: 99 } ) then schemas}
              {#each schemas.records.map((e) => e.shortname) as schema}
                <option value={schema}>{schema}</option>
              {/each}
            {/await}
          </Input>
          <JSONEditor
            onRenderMenu={handleRenderMenu}
            mode={Mode.text}
            bind:content={payloadContent}
          />
        {:else if resourceType === ResourceAttachmentType.comment}
          <Input type={"textarea"} bind:value={payloadData} />
        {:else if resourceType === ResourceAttachmentType.csv}
          <Label>Schema</Label>
          <Input bind:value={selectedSchema} type="select">
            <option value={null}>{"None"}</option>
            {#await query( { space_name, type: QueryType.search, subpath: "/schema", search: "", retrieve_json_payload: true, limit: 99 } ) then schemas}
              {#each setSchemaItems(schemas) as schema}
                <option value={schema}>{schema}</option>
              {/each}
            {/await}
          </Input>
          <Label class="mt-3">CSV File</Label>
          <Input bind:files={payloadFiles} type="file" accept=".csv" />
        {:else if resourceType === ResourceAttachmentType.jsonl}
          <Label>JSONL File</Label>
          <Input bind:files={payloadFiles} type="file" accept=".jsonl" />
        {:else if resourceType === ResourceAttachmentType.sqlite}
          <Label>SQLite File</Label>
          <Input
            bind:files={payloadFiles}
            type="file"
            accept=".sqlite,.sqlite3,.db,.db3,.s3db,.sl3"
          />
        {:else if resourceType === ResourceAttachmentType.parquet}
          <Label>Parquet File</Label>
          <Input bind:files={payloadFiles} type="file" accept=".parquet" />
          <b> TBD ... show custom fields for resource type : {resourceType} </b>
        {/if}
      {/key}
    </div>
  </ModalBody>
  <ModalFooter>
    <Button
      type="button"
      color="secondary"
      on:click={() => (openCreateAttachemntModal = false)}
      >close
    </Button>
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
    <JSONEditor
      onRenderMenu={handleRenderMenu}
      mode={Mode.text}
      {content}
      readOnly={true}
    />
  </ModalBody>
  <ModalFooter>
    <Button
      type="button"
      color="secondary"
      on:click={() => (openViewAttachmentModal = false)}
      >close
    </Button>
  </ModalFooter>
</Modal>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="d-flex justify-content-end mx-2 flex-row">
  <div
    on:click={() => {
      shortname = "auto";
      resourceType = ResourceAttachmentType.media;
      contentType = ContentType.image;

      openCreateAttachemntModal = true;
      isModalInUpdateMode = false;
    }}
  >
    <Icon style="cursor: pointer;" name="plus-square" />
  </div>
</div>

{#await fetchDataAssetsForAttachments()}
  Loading...
{:then _}
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
            target="_blank"
            rel="noopener noreferrer"
            download>{attachment.shortname}</a
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
                handleView(attachment);
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
            >
              <Icon name="code-slash" />
            </div>
            {#if [ContentType.markdown].includes(attachment.attributes.payload.content_type)}
              <!-- svelte-ignore a11y-click-events-have-key-events -->
              <!-- svelte-ignore a11y-no-static-element-interactions -->
              <div
                class="mx-1"
                style="cursor: pointer;"
                on:click={() => {
                  handleContentEditModal(attachment);
                }}
              >
                <Icon name="pencil-square" />
              </div>
            {/if}
            {#if [ResourceType.json, ResourceType.content, ResourceType.comment].includes(attachment.resource_type)}
              <!-- svelte-ignore a11y-click-events-have-key-events -->
              <!-- svelte-ignore a11y-no-static-element-interactions -->
              <div
                class="mx-1"
                style="cursor: pointer;"
                on:click={() => {
                  handleContentEditModal(attachment);
                }}
              >
                <Icon name="pencil" />
              </div>
            {/if}
          </div>
        </div>
        <div
          class="d-flex col"
          style="overflow: auto;max-height: 80vh;max-width: 80vw;"
        >
          {#if attachment}
            {#if [ResourceType.csv, ResourceType.jsonl, ResourceType.parquet, ResourceType.sqlite].includes(attachment.resource_type)}
              {#if attachment.dataAsset}
                {#if [ResourceType.parquet, ResourceType.csv].includes(attachment.resource_type)}
                  <table class="table table-striped table-sm">
                    <thead>
                      <tr>
                        {#each Object.keys(attachment.dataAsset[0]) as header (header)}
                          <th>{header}</th>
                        {/each}
                      </tr>
                    </thead>
                    <tbody>
                      {#each attachment.dataAsset as item}
                        <tr>
                          {#each Object.keys(attachment.dataAsset[0]) as key (key)}
                            <td>
                              {item[key]}
                            </td>
                          {/each}
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                {:else if attachment.resource_type === ResourceType.sqlite}
                  <Col>
                    {#each attachment.dataAsset ?? [] as dataAsset}
                      <h3>{dataAsset.table_name}</h3>
                      <table class="table table-striped table-sm">
                        <thead>
                          <tr>
                            {#each Object.keys(dataAsset.rows[0]) as header (header)}
                              <th>{header}</th>
                            {/each}
                          </tr>
                        </thead>
                        <tbody>
                          {#each dataAsset.rows as item}
                            <tr>
                              {#each Object.keys(dataAsset.rows[0]) as key (key)}
                                <td>
                                  {item[key]}
                                </td>
                              {/each}
                            </tr>
                          {/each}
                        </tbody>
                      </table>
                    {/each}
                  </Col>
                {:else if attachment.resource_type === ResourceType.jsonl}
                  <div class="w-100">
                    <Prism code={attachment.dataAsset} />
                  </div>
                {/if}
              {/if}
            {:else if attachment.resource_type === ResourceType.media }
              <Media
                resource_type={ResourceType[attachment.resource_type]}
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
            {:else}
              {#await get_attachment_content(attachment.resource_type, space_name, `${subpath}/${parent_shortname}`, attachment.attributes?.payload?.body)}
                loading...
              {:then response}
                {#if attachment.resource_type === ResourceType.csv}
                  {#await parseCSV(response)}
                    Parsing...
                  {:then { headers, rows }}
                    <table class="table table-striped table-sm">
                      <thead>
                        <tr>
                          {#each headers as header}
                            <th>{header}</th>
                          {/each}
                        </tr>
                      </thead>
                      <tbody>
                        {#each rows as row}
                          <tr>
                            {#each headers as header}
                              <td>{row[header]}</td>
                            {/each}
                          </tr>
                        {/each}
                      </tbody>
                    </table>
                  {/await}
                {:else if attachment.resource_type === ResourceType.jsonl}
                  <div
                    class="d-flex row"
                    style=" max-height: 50vh;overflow-y: scroll;"
                  >
                    {#each parseJSONL(response) as item}
                      <Prism code={item} />
                    {/each}
                  </div>
                {:else if attachment.resource_type === ResourceType.parquet}
                  <pre>{@html response}</pre>
                {:else}
                  <Prism code={response} />
                {/if}
              {/await}
            {/if}
          {/if}
        </div>
      </div>
      <hr />
    {/each}
  </div>
{/await}
