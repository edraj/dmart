<script>
  import Fa from "sveltejs-fontawesome";
  import { faTrashCan, faEye } from "@fortawesome/free-regular-svg-icons";
  import { dmart_entry } from "../dmart";
  import {
    Button,
    Modal,
    ModalBody,
    ModalFooter,
    ModalHeader,
  } from "sveltestrap";
  import ContentJsonEditor from "./ContentJsonEditor.svelte";

  export let attachments;
  let content;
  export let space_name;

  let _attachments = [];

  let open = false;
  function toggle() {
    open = !open;
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
    open = true;
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
                link: await dmart_entry(
                  element.resource_type,
                  space_name,
                  element.subpath,
                  element.shortname,
                  "",
                  getFileExtension(element.attributes.payload.body),
                  type
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
</script>

<Modal isOpen={open} {toggle} size={"lg"}>
  <ModalHeader />
  <ModalBody>
    <ContentJsonEditor bind:content />
  </ModalBody>
  <ModalFooter>
    <Button type="button" color="secondary" on:click={() => (open = false)}
      >close</Button
    >
  </ModalFooter>
</Modal>

<div class="row mx-auto w-75">
  {#await init}
    <p>...</p>
  {:then _}
    {#each _attachments as attachment}
      <hr />
      <div class="row">
        <p class="col-11" style="font-size: 1.25em;">{attachment.title}</p>
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
        <img class="border" src={attachment.link} alt={attachment.title} />
      {/if}
      {#if attachment.type === "pdf"}
        <object
          title={attachment.title}
          class="w-100 embed-responsive-item"
          style="height: 100vh;"
          type="application/pdf"
          data={attachment.link}
        >
          <p>For some reason PDF is not rendered here properly.</p>
        </object>
      {/if}
      <hr />
    {/each}
  {:catch error}
    <p style="color: red">{error.message}</p>
  {/await}
</div>
