<script>
  import Fa from "sveltejs-fontawesome";
  import { Circle2 } from "svelte-loading-spinners";
  import {
    faTrashCan,
    faEye,
    faPlusSquare,
  } from "@fortawesome/free-regular-svg-icons";
  import {
    ctorULRForAttachment,
    dmartEntry,
    dmarRresourceWithPayload,
  } from "../dmart";
  import {
    Button,
    Input,
    Label,
    Modal,
    ModalBody,
    ModalFooter,
    ModalHeader,
  } from "sveltestrap";
  import ContentJsonEditor from "./ContentJsonEditor.svelte";
  import { toastPushFail, toastPushSuccess } from "../utils";
  import AudioPlayer from "./AudioPlayer.svelte";

  export let attachments;
  export let space_name;
  export let subpath;
  export let entryShortname;
  let content;
  let shortname;

  let _attachments = [];

  let openViewAttachmentModal = false;
  function toggleViewAttachmentModal() {
    openViewAttachmentModal = !openViewAttachmentModal;
  }

  let openCreateAttachemntModal = false;
  function toggleCreateAttachemntModal() {
    openCreateAttachemntModal = !openCreateAttachemntModal;
  }

  function getFileExtension(filename) {
    var ext = /^.+\.([^.]+)$/.exec(filename);
    return ext == null ? "" : ext[1];
  }

  function handleDelete(params) {}
  function handleView(attachemntTitle) {
    content = {
      json: attachments.media.filter((e) => e.shortname === attachemntTitle)[0],
      text: undefined,
    };
    openViewAttachmentModal = true;
  }

  async function initAttachments() {
    try {
      await Promise.all(
        Object.keys(attachments).map(async (content_type) => {
          await Promise.all(
            attachments[content_type].map(async (element) => {
              const type = element.attributes.payload.content_type;
              _attachments.push({
                type,
                title: element.shortname,
                content: await dmartEntry(
                  element.resource_type,
                  space_name,
                  element.subpath,
                  element.shortname,
                  "",
                  getFileExtension(element.attributes.payload.body),
                  type
                ),
                link: ctorULRForAttachment(
                  element.resource_type,
                  space_name,
                  element.subpath,
                  element.shortname,
                  "",
                  getFileExtension(element.attributes.payload.body)
                ),
              });

              return element;
            })
          );
          return content_type;
        })
      );
    } catch (error) {
      console.log({ error });
    }
  }
  let init = initAttachments();

  function jsonToFile(obj) {
    console.log({ obj });
    return new Blob([JSON.stringify(obj)], { type: "application/json" });
  }

  let requestRecord, payloadFile;
  async function upload() {
    const response = await dmarRresourceWithPayload(
      space_name,
      jsonToFile({
        resource_type: "media",
        subpath: subpath + "/" + entryShortname,
        shortname,
        attributes: {
          is_active: true,
        },
      }),
      payloadFile[0]
    );
    if (response.status === "success") {
      toastPushSuccess();
      openCreateAttachemntModal = false;
    } else {
      toastPushFail();
    }
  }
</script>

<Modal
  isOpen={openCreateAttachemntModal}
  toggle={toggleCreateAttachemntModal}
  size={"lg"}
>
  <ModalHeader>
    <h3>Add attachment</h3>
  </ModalHeader>
  <ModalBody>
    <div class="d-flex flex-column">
      <Label>Request Record</Label>
      <Input accept="image/png, image/jpeg" bind:value={shortname} />
      <hr />
      <Label>Payload File</Label>
      <Input
        accept="image/png, image/jpeg"
        bind:files={payloadFile}
        type="file"
      />
    </div>
  </ModalBody>
  <ModalFooter>
    <Button
      type="button"
      color="secondary"
      on:click={() => (openCreateAttachemntModal = false)}>close</Button
    >
    <Button type="button" color="primary" on:click={async () => upload()}
      >Upload</Button
    >
  </ModalFooter>
</Modal>

<Modal
  isOpen={openViewAttachmentModal}
  toggle={toggleViewAttachmentModal}
  size={"lg"}
>
  <ModalHeader />
  <ModalBody>
    <ContentJsonEditor bind:content readOnly={true} />
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
<div
  class="d-flex justify-content-end mx-2 flex-row"
  on:click={toggleCreateAttachemntModal}
>
  <Fa icon={faPlusSquare} size={"3x"} color={"grey"} />
</div>

<div class="row mx-auto w-75">
  {#await init}
    <Circle2 size="200" color="#FF3E00" unit="px" duration="1s" />
  {:then _}
    <div class="d-flex justify-content-center" />
    {#each _attachments as attachment}
      <hr />
      <div class="row mb-2">
        <a class="col-11" style="font-size: 1.25em;" href={attachment.link}
          >{attachment.title}</a
        >
        <div class="col-1 d-flex justify-content-between">
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <div class="mx-1" on:click={() => handleDelete(attachment)}>
            <Fa icon={faTrashCan} size="2x" color="red" />
          </div>
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <div class="mx-1" on:click={() => handleView(attachment.title)}>
            <Fa icon={faEye} size="2x" color="grey" />
          </div>
        </div>
      </div>

      {#if attachment.type === "image"}
        <img class="border" src={attachment.content} alt={attachment.title} />
      {/if}
      {#if attachment.type === "pdf"}
        <object
          title={attachment.title}
          class="w-100 embed-responsive-item"
          style="height: 100vh;"
          type="application/pdf"
          data={attachment.content}
        >
          <p>For some reason PDF is not rendered here properly.</p>
        </object>
      {/if}
      {#if attachment.type === "audio"}
        <AudioPlayer src={attachment.link} />
      {/if}
      <hr />
    {/each}
  {:catch error}
    <p style="color: red">{error.message}</p>
  {/await}
</div>
