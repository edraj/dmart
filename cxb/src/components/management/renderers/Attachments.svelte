<script lang="ts">
    import {ContentType, Dmart, RequestType, ResourceType,} from "@edraj/tsdmart";
    import {Level, showToast} from "@/utils/toast";
    import {Badge, Button, Card, CardPlaceholder, Dropdown, DropdownItem, Modal,} from "flowbite-svelte";
    import {JSONEditor, Mode} from "svelte-jsoneditor";
    import {AxiosError} from "axios";
    import {
        DotsHorizontalOutline,
        EyeOutline,
        EyeSolid,
        FileCsvOutline,
        FileImageOutline,
        FileLinesOutline,
        FileLinesSolid,
        FileMusicSolid,
        FileOutline,
        FileVideoSolid,
        ListOutline,
        PenSolid,
        TrashBinSolid,
        UploadOutline
    } from "flowbite-svelte-icons";
    import ModalViewAttachments from "@/components/management/Modals/ModalViewAttachments.svelte";
    import {getFileExtension} from "@/utils/getFileExtension";
    import ModalCreateAttachments from "@/components/management/Modals/ModalCreateAttachments.svelte";
    import {currentEntry} from "@/stores/global";
    import {untrack} from "svelte";


    let {
    attachments = [],
    resource_type,
    space_name,
    subpath,
    parent_shortname,
  } :{
    attachments: any,
    resource_type: ResourceType,
    space_name: string,
    subpath: string,
    parent_shortname: string,
    refreshEntry: any,
  } = $props();


  async function fetchDataAssetsForAttachments() {
    for (const attachment of filteredAttachments) {
      if (["csv", "parquet", "jsonl"].includes(attachment.resource_type)) {
        const r = await Dmart.fetchDataAsset({
            resourceType: resource_type,
            dataAssetType: attachment.resource_type,
            spaceName: space_name,
            subpath: subpath,
            shortname: parent_shortname,
            query_string: `SELECT * FROM '${attachment.shortname}'`
      });
        if (!(r instanceof AxiosError)) {
          attachment.dataAsset = r;
        } else {
          attachment.dataAsset = {
            code: r.response.data?.error?.code,
            message: r.response.data?.error?.message,
          };
          if(r.response.data?.error?.info.length > 0) {
              attachment.dataAsset.details = r.response.data?.error?.info[0].msg;
          }
        }
      } else if (attachment.resource_type === "sqlite") {
        const tables = await Dmart.fetchDataAsset(
            {
                resourceType: resource_type,
                dataAssetType: attachment.resource_type,
                spaceName: space_name,
                subpath,
                shortname: parent_shortname,
                query_string: "SELECT * FROM temp.information_schema.tables",
                filter_data_assets: [attachment.shortname]
            }
        );
        attachment.dataAsset = (
          await Promise.all(
            tables.map(async (table) => {
              const r = await Dmart.fetchDataAsset({
                  resourceType: resource_type,
                  dataAssetType: attachment.resource_type,
                  spaceName: space_name,
                  subpath: subpath,
                  shortname: parent_shortname,
                  query_string: `SELECT * FROM '${table.table_name}' LIMIT 10`,
                  filter_data_assets: [attachment.shortname]
            });
              return r instanceof AxiosError
                ? null
                : { table_name: table.table_name, rows: r };
            })
          )
        ).filter((item) => item !== null);
      }
    }
  }

  let shortname = $state("auto");
  let isModalInUpdateMode = $state(false);
  let openViewAttachmentModal = $state(false);

  let content = $state({
    json: {},
    text: undefined,
  });

  let isDeleteLoading = $state(false);
  async function handleDelete(item: {
    shortname: string;
    subpath: string;
    resource_type: ResourceType;
  }) {
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
    try {
      isDeleteLoading = true;
      const response = await Dmart.request(request_dict);
      if (response.status === "success") {
        showToast(Level.info, `Attachment ${item.shortname} deleted successfully.`);
        $currentEntry.refreshEntry();
        openCreateAttachmentModal = false;
      } else {
        showToast(Level.warn);
      }
    } catch (e) {
      showToast(Level.warn);
    } finally {
      isDeleteLoading = false;
      openDeleteModal = false;
    }
  }

  function handleEditModal(attachment) {
    selectedAttachment = attachment;
    isModalInUpdateMode = true;
    openCreateAttachmentModal = true;
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

  function viewMeta(attachment) {
    selectedAttachment = attachment;
    content = {
      json: attachment,
      text: undefined,
    };
    openViewAttachmentModal = true;
  }

  function editAttachment(attachment) {
    selectedAttachment = attachment;

    // Only update payload for json, text, comment, markdown, html types
    // if (attachment.resource_type === ResourceType.json
    //     || [ContentType.text, ContentType.json, ContentType.markdown, ContentType.html].includes(attachment.attributes?.payload?.content_type)
    //     || attachment.resource_type === ResourceType.comment) {
    //   handleContentEditModal(attachment);
    // } else {
    //   // For all other types, only update metadata
    //   handleMetaEditModal(attachment);
    // }

    handleEditModal(selectedAttachment);
  }

  function confirmDelete(attachment) {
    selectedAttachment = attachment;
    openDeleteModal = true;
  }

  let openDeleteModal = $state(false);
  let openViewContentModal = $state(false);
  let openCreateAttachmentModal = $state(false);
  let selectedAttachment = $state(null);

  function handleViewContentModal(attachment) {
    selectedAttachment = attachment;
    openViewContentModal = true;
  }

  $effect(()=>{
    if(selectedFilter === "all") {
      filteredAttachments = Object.values(attachments).flat(1);
    } else {
        filteredAttachments = attachments[selectedFilter] || [];
    }
  });

  let createMetaContent = $state({});
  let createPayloadContent = $state({});
  function handleCreateAttachmentModal(e){
    e.stopPropagation();
    isModalInUpdateMode=false;
    selectedAttachment = null;
    createMetaContent = {};
    createPayloadContent = {};
    openCreateAttachmentModal = true;
  }

  let selectedFilter = $state("all");
  let filteredAttachments: any = $state(Object.values(attachments).flat(1));
  let contentTypeGroups: any = $state({});

  function groupAttachmentsByContentType() {
    const allAttachments = Object.values(attachments).flat(1);
    const groups = { all: allAttachments };

    allAttachments.forEach((attachment:any) => {
      let contentType = "other";

      if (attachment.resource_type === ResourceType.media && attachment.attributes?.payload?.content_type) {
        contentType = attachment.attributes.payload.content_type;
      } else if (attachment.resource_type === ResourceType.csv) {
        contentType = "csv";
      } else if (attachment.resource_type === ResourceType.json) {
        contentType = "json";
      } else if (attachment.resource_type === ResourceType.comment) {
        contentType = "comment";
      }

      groups[contentType] = groups[contentType] || [];
      groups[contentType].push(attachment);
    });

    return groups;
  }
  $effect(() => {
    contentTypeGroups = groupAttachmentsByContentType();
    untrack(()=>{
      filteredAttachments = contentTypeGroups[selectedFilter] || contentTypeGroups.all;
    })
  });
  $effect(() => {
      if (selectedFilter) {
        untrack(()=>{
          filteredAttachments = contentTypeGroups[selectedFilter] || contentTypeGroups.all;
        })
      }
  });
</script>


<Modal
  bind:open={openViewAttachmentModal}
  size={"lg"}
>
  <div class="p-6">
    <JSONEditor
      onRenderMenu={handleRenderMenu}
      mode={Mode.text}
      {content}
      readOnly={true}
    />
  </div>
</Modal>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="d-flex justify-content-between mx-2 flex-row">

</div>

{#await fetchDataAssetsForAttachments()}
  <div class="flex flex-row">
    <CardPlaceholder size="md" class="mt-8" />
    <CardPlaceholder size="md" class="mt-8" />
    <CardPlaceholder size="md" class="mt-8" />
  </div>
{:then _}
  <div class="d-flex justify-content-center flex-column px-5 mt-2">
    <div class="flex justify-between">
      <div>
        <Badge class={selectedFilter === "all" ? "m-1 bg-primary text-white" : "m-1 bg-[#F5F5FF] text-primary"}
               style="cursor: pointer;"
               onclick={() => { selectedFilter = 'all'; }}
        >
          <ListOutline size="lg" />
          ALL ({contentTypeGroups.all?.length || 0})
        </Badge>

        {#each Object.keys(contentTypeGroups).filter(key => key !== 'all') as contentType}
          <Badge class={selectedFilter === contentType ? "m-1 bg-primary text-white" : "m-1 bg-[#F5F5FF] text-black"}
                 style="cursor: pointer;"
                 onclick={() => { selectedFilter = contentType; }}
          >
        <span class="inline-flex items-center gap-2">
          {#if contentType === ContentType.image}
            <FileImageOutline size="lg" />
          {:else if contentType === ContentType.audio}
            <FileMusicSolid size="lg" />
          {:else if contentType === ContentType.video}
            <FileVideoSolid size="lg" />
          {:else if contentType === ContentType.text || contentType === ContentType.markdown || contentType === ContentType.html}
            <FileLinesSolid size="lg" />
          {:else if contentType === "csv"}
            <FileCsvOutline size="lg" />
          {:else}
            <FileOutline size="lg" />
          {/if}
          {contentType.toUpperCase()} ({contentTypeGroups[contentType]?.length || 0})
        </span>
          </Badge>
        {/each}
      </div>

      <!-- Keep the upload button as is -->
      <Button class="text-primary cursor-pointer hover:bg-primary hover:text-white" outline
              onclick={handleCreateAttachmentModal}>
        <UploadOutline size="md" class="mr-2"/>
        <strong>UPLOAD</strong>
      </Button>
    </div>

    <div class="my-5 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-4 gap-4 w-full place-items-center">
      {#each filteredAttachments as attachment}
      <Card class="relative w-full">
        <div class="absolute top-2 left-2">
          <Button class="!p-1" color="light">
            <DotsHorizontalOutline />
            <Dropdown simple>
              <DropdownItem class="w-full" onclick={() => viewMeta(attachment)}>
                <div class="flex items-center gap-2">
                  <EyeSolid size="sm" /> View Meta
                </div>
              </DropdownItem>
              <DropdownItem class="w-full" onclick={() => editAttachment(attachment)}>
                <div class="flex items-center gap-2">
                  <PenSolid size="sm" /> Edit
                </div>
              </DropdownItem>
              <DropdownItem class="w-full" onclick={() => confirmDelete(attachment)}>
                <div class="flex items-center gap-2 text-red-600">
                  <TrashBinSolid size="sm" /> Delete
                </div>
              </DropdownItem>
            </Dropdown>
          </Button>
        </div>

        <div class="flex flex-col items-center text-center p-4">
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <span class="inline-block px-3 py-1 mb-3 border border-gray-300 rounded-md text-sm font-medium bg-primary">
            {#if attachment.resource_type === ResourceType.media}
              {#if attachment.attributes?.payload.content_type === ContentType.image}
                <FileImageOutline size="xl" class="text-white" />
              {:else if attachment.attributes?.payload.content_type === ContentType.audio}
                <FileMusicSolid size="xl" class="text-white" />
              {:else if attachment.attributes?.payload.content_type === ContentType.video}
                <FileVideoSolid size="xl" class="text-white" />
              {:else if [ContentType.text,ContentType.markdown, ContentType.html].includes(attachment.attributes?.payload.content_type)}
                <FileLinesSolid size="xl" class="text-white" />
              {:else}
                <FileOutline size="xl" class="text-white" />
              {/if}
            {:else if attachment.resource_type === ResourceType.csv}
              <FileCsvOutline size="xl" class="text-white"/>
            {:else if [ResourceType.comment, ResourceType.json].includes(attachment.resource_type)}
              <FileLinesOutline size="xl" class="text-white"/>
            {:else}
              <FileOutline size="xl" class="text-white" />
            {/if}
          </span>
          {#if attachment.resource_type === ResourceType.media}
            <a class="font-semibold text-lg underline text-primary" href={Dmart.getAttachmentUrl({
                resource_type: attachment.resource_type, space_name, subpath,
                parent_shortname: (resource_type === ResourceType.folder ? '' : parent_shortname),
                shortname: attachment.shortname,
                ext: getFileExtension(attachment.attributes?.payload?.body)
            })} target="_blank">{attachment.attributes?.displayname?.en || attachment.shortname}</a>
            {:else}
            <p class="font-semibold text-lg">
              {attachment.attributes?.displayname?.en || attachment.shortname}
            </p>
          {/if}
          <p class="text-gray-600 mt-2 mb-4 line-clamp-3">
            {attachment.attributes?.description?.en || ""}
          </p>

          <div class="text-xs text-gray-500 mt-auto">
            Type: {attachment.resource_type} ({attachment.attributes?.payload.content_type ?? "N/A"})
            <br>
            Updated: {new Date(attachment?.attributes.updated_at).toLocaleDateString()}
          </div>
        </div>
        {#if attachment.resource_type !== ResourceType.reaction}
          <div class="absolute top-2 right-2" onclick={() => handleViewContentModal(attachment)}>
            <Button class="!p-1" color="light">
              <EyeOutline />
            </Button>
          </div>
        {/if}
      </Card>
    {/each}
    </div>
  </div>
{/await}


<ModalViewAttachments
  bind:openViewContentModal={openViewContentModal}
  selectedAttachment={selectedAttachment}
  space_name={space_name}
  subpath={subpath}
  parent_resource_type={resource_type}
  parent_shortname={parent_shortname}
/>

<ModalCreateAttachments
  bind:isOpen={openCreateAttachmentModal}
  isUpdateMode={isModalInUpdateMode}
  selectedAttachment={selectedAttachment}
  parentResourceType={resource_type}
  space_name={space_name}
  subpath={subpath}
  parent_shortname={parent_shortname}
  bind:meta={createMetaContent}
  bind:payload={createPayloadContent}
/>

<Modal bind:open={openDeleteModal} size="md" title="Confirm Deletion">
  {#if selectedAttachment}
    <p class="text-center mb-6">
      Are you sure you want to delete the attachment <span class="font-bold">{selectedAttachment.shortname}</span>?<br>
      This action cannot be undone.
    </p>
  {/if}

  <div class="flex justify-between w-full">
    <Button color="alternative" onclick={() => openDeleteModal = false}>Cancel</Button>
    <Button color="red" onclick={() => handleDelete(selectedAttachment)} disabled={isDeleteLoading}>{isDeleteLoading ? "Deleting..." : "Delete"}</Button>
  </div>
</Modal>
