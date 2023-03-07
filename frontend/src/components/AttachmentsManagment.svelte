<script>
  import Fa from "sveltejs-fontawesome";
  import { faTrashCan } from "@fortawesome/free-regular-svg-icons";
  import { dmart_entry } from "../dmart";

  export let content;
  export let space_name;

  let attachments = [];

  function getFileExtension(filename) {
    var ext = /^.+\.([^.]+)$/.exec(filename);
    return ext == null ? "" : ext[1];
  }

  function handleDelete(params) {}

  async function initAttachments() {
    try {
      await Promise.all(
        Object.keys(content).map(async (content_type) => {
          await Promise.all(
            content[content_type].map(async (element) => {
              const type = element.attributes.payload.content_type;
              attachments.push({
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

<div class="row mx-auto w-75">
  {#await init}
    <p>...</p>
  {:then _}
    {#each attachments as attachment}
      <hr />
      <div class="row">
        <p class="col-10" style="font-size: 1.25em;">{attachment.title}</p>
        <div class="col-2 d-flex justify-content-end">
          <Fa
            icon={faTrashCan}
            size="2x"
            color="red"
            on:click={() => handleDelete(attachment)}
          />
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
