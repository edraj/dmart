<script lang="ts">
  import { goto } from "@roxi/routify";
  $goto
  import {
    space,
    get_children,
    type ApiResponseRecord,
    RequestType,
    ResourceType,
    get_spaces,
  } from "@/dmart";
  import {
    Form,
    FormGroup,
    Button,
    Modal,
    ModalBody,
    ModalFooter,
    ModalHeader,
    Label,
    Input,
    ListGroupItem,
  } from "sveltestrap";
  import Icon from "../../Icon.svelte";
  import Folder from "../Folder.svelte";
  import { Level, showToast } from "@/utils/toast";
  import refresh_spaces from "@/stores/management/refresh_spaces";

  let expanded: string = $state(undefined);
  function displayname(space_entry: ApiResponseRecord): string {
    let lang = null;
    if (typeof localStorage !== 'undefined') {
        lang = JSON.parse(localStorage.getItem("preferred_locale"));
    }if (space_entry?.attributes?.displayname && lang in space_entry?.attributes?.displayname) {
      return (
        space_entry?.attributes?.displayname[lang] ?? space_entry.shortname
      );
    } else {
      return space_entry.shortname;
    }
  }

  async function expandSpace(current_space: ApiResponseRecord) {
    if (expanded != current_space.shortname) {
      expanded = current_space.shortname;
      $goto("/management/content/[space_name]", {
        space_name: current_space.shortname,
      });
    } else {
      expanded = undefined;
    }
  }

  let isSpaceModalOpen = $state(false);
  let space_name_shortname =$state("") ;
  // let refresh : boolean = false;
  async function handleCreateSpace(e: Event) {
    e.preventDefault();

    const request_body = {
      space_name: space_name_shortname,
      request_type: RequestType.create,
      records: [
        {
          resource_type: ResourceType.space,
          subpath: "/",
          shortname: space_name_shortname,
          attributes: {},
        },
      ],
    };
    const response = await space(request_body);
    if (response.status === "success") {
      showToast(Level.info);
      isSpaceModalOpen = false;

      refresh_spaces.refresh();
      space_name_shortname = "";
    } else {
      showToast(Level.warn);
    }
  }
  let canCreateNewSpace = $state(false);
  $effect(() => {
    let permissions = [];
    if (typeof localStorage !== 'undefined')
      permissions = JSON.parse(localStorage.getItem("permissions"));
    if (permissions === null || Object.keys(permissions).length === 0) {
      canCreateNewSpace = false;
    }

    const k = "__all_spaces__:__all_subpaths__:space";
    if (Object.keys(permissions).includes(k)) {
      canCreateNewSpace = permissions[k].allowed_actions.includes("create");
    }
  });

  const toggleModal = () => {
      isSpaceModalOpen = !isSpaceModalOpen;
  }
</script>

{#key $refresh_spaces}
  {#await get_spaces()}
    <!--h3 transition:fade >Loading spaces list</h3-->
  {:then loaded_spaces}
    {#if loaded_spaces}
      {#each loaded_spaces.records as space}
        <ListGroupItem class="ps-2 pe-0 py-0">
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <div
            class="hover mb-2"
            style="cursor: pointer;"
            onclick={async () => await expandSpace(space)}
          >
            <Icon name="diagram-3" class="me-1" /> <b>{displayname(space)}</b>
            <style>
              .toolbar {
                /* display: none; */
                color: brown;
              }

              .toolbar span:hover {
                color: green;
              }
            </style>
          </div>

          {#if expanded === space.shortname}
            {#await get_children( space.shortname, "/", 10, 0, [ResourceType.folder] )}
              <!--h4> Loading {space.shortname} </h4-->
            {:then children_data}
              {#each (children_data?.records ?? []) as folder}
                <Folder {folder} space_name={space.shortname} />
              {/each}
            {:catch error}
              <p style="color: red">{error.message}</p>
            {/await}
          {/if}
        </ListGroupItem>
      {/each}
    {:else}
      <p>Can't load spaces!</p>
    {/if}
  {:catch error}
    <p style="color: red">{error.message}</p>
  {/await}
{/key}
{#if canCreateNewSpace}
  <ListGroupItem><Button
    class="w-100"
    type="button"
    outline
    color="primary"
    onclick={() => {
      isSpaceModalOpen = true;
    }}>Create new space</Button
  ></ListGroupItem>
{/if}

<Modal
  isOpen={isSpaceModalOpen}
  toggle={toggleModal}
  size={"lg"}
>
  <ModalHeader toggle={toggleModal}/>
  <Form on:submit={(e) => handleCreateSpace(e)}>
    <ModalBody>
      <FormGroup>
        <Label class="mt-3">Space name</Label>
        <Input bind:value={space_name_shortname} type="text" />
      </FormGroup>
    </ModalBody>
    <ModalFooter>
      <Button
        type="button"
        color="secondary"
        onclick={() => (isSpaceModalOpen = false)}>cancel</Button
      >
      <Button type="submit" color="primary">Submit</Button>
    </ModalFooter>
  </Form>
</Modal>

<style>
  div.hover:hover {
    background-color: #b7b7b7;
  }
</style>
