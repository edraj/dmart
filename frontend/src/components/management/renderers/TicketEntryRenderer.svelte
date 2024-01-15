<script lang="ts">
  import Attachments from "../Attachments.svelte";
  import { onMount, onDestroy } from "svelte";
  import {
    QueryType,
    RequestType,
    ResourceType,
    ResponseEntry,
    Status,
    get_payload,
    progress_ticket,
    query,
    request,
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
      Nav,
      ButtonGroup, TabContent, TabPane,
  } from "sveltestrap";
  import Icon from "@/components/Icon.svelte";
  import { _ } from "../../../i18n";
  import ListView from "@/components/management/ListView.svelte";
  import Prism from "@/components/Prism.svelte";
  import {
    JSONEditor,
    Mode,
    Validator,
    createAjvValidator,
  } from "svelte-jsoneditor";
  import { status_line } from "@/stores/management/status_line";
  import { timeAgo } from "@/utils/timeago";
  import { showToast, Level } from "@/utils/toast";
  import { faSave } from "@fortawesome/free-regular-svg-icons";
  import history_cols from "@/stores/management/list_cols_history.json";
  import metaTicketSchema from "@/validations/meta.ticket.json";
  import { isDeepEqual, removeEmpty } from "@/utils/compare";
  import checkAccess from "@/utils/checkAccess";
  import { fade } from "svelte/transition";
  import BreadCrumbLite from "../BreadCrumbLite.svelte";
  import { goto } from "@roxi/routify";
  import SchemaForm from "svelte-jsonschema-form";
  import Table2Cols from "@/components/management/Table2Cols.svelte";
  import {cleanUpSchema} from "@/utils/renderer/rendererUtils";

  let header_height: number;
  export let entry: ResponseEntry;
  export let space_name: string;
  export let subpath: string;
  export let resource_type: ResourceType;
  export let schema_name: string | undefined = null;

  const canUpdate = checkAccess("update", space_name, subpath, resource_type);
  const canDelete = checkAccess("delete", space_name, subpath, resource_type);
  const userRoles = JSON.parse(localStorage.getItem("roles"));

  let tab_option = resource_type === ResourceType.folder ? "list" : "view";
  let content = { json: entry, text: undefined };
  let contentMeta = { json: {}, text: undefined };
  let validatorMeta: Validator = createAjvValidator({
    schema: metaTicketSchema,
  });
  let oldContentMeta = { json: entry || {}, text: undefined };

  let contentContent = { json: {}, text: undefined };
  let validator: Validator = createAjvValidator({ schema: {} });
  let oldContent = { json: {}, text: undefined };
  let entryContent;

  onMount(async () => {
    const cpy = JSON.parse(JSON.stringify(entry));

    if (contentContent === null) {
      contentContent = { json: {}, text: undefined };
    }
    contentContent.json = cpy?.payload?.body ?? {};
    contentContent = structuredClone(contentContent);
    oldContent = structuredClone(contentContent);

    delete cpy?.payload?.body;
    delete cpy?.attachments;
    contentMeta.json = cpy;
    contentMeta = structuredClone(contentMeta);
    oldContentMeta = structuredClone(contentMeta);
  });

  onDestroy(() => status_line.set(""));
  status_line.set(
    `<small>Last updated: <strong>${timeAgo(
      new Date(entry.updated_at)
    )}</strong><br/>Attachments: <strong>${
      Object.keys(entry.attachments).length
    }</strong></small>`
  );

  let isSchemaValidated: boolean;
  function handleChange(updatedContent, previousContent, patchResult) {
    const v = patchResult?.contentErrors?.validationErrors;
    if (v === undefined || v.length === 0) {
      isSchemaValidated = true;
    } else {
      isSchemaValidated = false;
    }
  }

  let schemaFormRef;
  let errorContent = null;
  async function handleSave(e) {
    e.preventDefault();
    // if (!isSchemaValidated) {
    //   alert("The content does is not validated agains the schema");
    //   return;
    // }

    if (!schemaFormRef.reportValidity()) {
      return;
    }

    errorContent = null;

    const x = contentMeta.json
      ? structuredClone(contentMeta.json)
      : JSON.parse(contentMeta.text);

    let data;

    const y = contentContent.json
      ? structuredClone(contentContent.json)
      : JSON.parse(contentContent.text);

    data = structuredClone(x);
    data.payload.body = y;

    const response = await request({
      space_name: space_name,
      request_type: RequestType.replace,
      records: [
        {
          resource_type,
          shortname: entry.shortname,
          subpath,
          attributes: data,
        },
      ],
    });
    if (response.status === Status.success) {
      showToast(Level.info);
      oldContentMeta = structuredClone(contentMeta);
      oldContent = structuredClone(contentContent);

      if (data.shortname !== entry.shortname) {
        const moveAttrb = {
          src_subpath: subpath,
          src_shortname: entry.shortname,
          dest_subpath: subpath,
          dest_shortname: data.shortname,
        };
        const response = await request({
          space_name: space_name,
          request_type: RequestType.move,
          records: [
            {
              resource_type,
              shortname: entry.shortname,
              subpath,
              attributes: moveAttrb,
            },
          ],
        });
        if (response.status === Status.success) {
          showToast(Level.info);
          if (entry?.payload?.schema_shortname) {
            $goto(
              "/management/content/[space_name]/[subpath]/[shortname]/[resource_type]/[payload_type]/[schema_name]",
              {
                space_name: space_name,
                subpath,
                shortname: data.shortname,
                resource_type,
                payload_type: entry?.payload?.content_type,
                schema_name: entry.payload.schema_shortname,
              }
            );
          } else {
            $goto(
              "/management/content/[space_name]/[subpath]/[shortname]/[resource_type]",
              {
                space_name: space_name,
                subpath,
                shortname: data.shortname,
                resource_type,
              }
            );
          }
        } else {
          errorContent = response;
          showToast(Level.warn);
        }
      }

        window.location.reload();
    } else {
      errorContent = response;
      showToast(Level.warn);
    }
  }

  function handleRenderMenu(items, context) {
    items = items.filter(
        (item) => !["tree", "text", "table"].includes(item.text)
    );
    const separator = {
      separator: true,
    };

    const saveButton = {
      onClick: handleSave,
      icon: faSave,
      title: "Save",
    };

    const itemsWithoutSpace = items.slice(0, items.length - 2);
    return itemsWithoutSpace.concat([
      separator,
      saveButton,
      {
        space: true,
      },
    ]);
  }

  let schema = null;
  async function get_schema() {
    const payload = await get_payload(
      ResourceType.content,
      space_name,
      "workflows",
      entry.workflow_shortname
    );

    if (entry.payload && entry.payload.schema_shortname) {
      const query_schema = {
        space_name,
        type: QueryType.search,
        subpath: "/schema",
        filter_shortnames: [entry.payload.schema_shortname],
        search: "",
        retrieve_json_payload: true,
      };

      const schema_data = await query(query_schema);
      if (schema_data.status === "success" && schema_data.records.length > 0) {
        schema = schema_data.records[0].attributes["payload"].body;
        cleanUpSchema(schema.properties);
        validator = createAjvValidator({ schema });
      }
    } else {
      schema = null;
    }
  }

  let isModalOpen = false;
  let modalFlag = "create";
  let entryType = "folder";
  let contentShortname = "";
  let selectedSchema = "";

  async function handleSubmit(e) {
    e.preventDefault();
    let response;
    if (entryType === "content") {
      const body = entryContent.json
        ? structuredClone(entryContent.json)
        : JSON.parse(entryContent.text);
      const request_body = {
        space_name,
        request_type: RequestType.create,
        records: [
          {
            resource_type: ResourceType.content,
            shortname: contentShortname === "" ? "auto" : contentShortname,
            subpath,
            attributes: {
              is_active: true,
              payload: {
                content_type: "json",
                schema_shortname: selectedSchema ? selectedSchema : "",
                body,
              },
            },
          },
        ],
      };
      response = await request(request_body);
    }
    else if (entryType === "folder") {
      const request_body = {
        space_name,
        request_type: RequestType.create,
        records: [
          {
            resource_type: ResourceType.folder,
            shortname: contentShortname === "" ? "auto" : contentShortname,
            subpath,
            attributes: {
              is_active: true,
            },
          },
        ],
      };
      response = await request(request_body);
    }
    if (response.status === "success") {
      showToast(Level.info);
      window.location.reload();
    }
    else {
      showToast(Level.warn);
    }
  }
  $: {
    if (
      schema === null &&
      entry &&
      entry.payload &&
      entry.payload.schema_shortname
    ) {
      get_schema();
    }
  }

  async function handleDelete() {
    if (
      confirm(`Are you sure want to delete ${entry.shortname} entry`) === false
    ) {
      return;
    }
    const request_body = {
      space_name,
      request_type: RequestType.delete,
      records: [
        {
          resource_type,
          shortname: entry.shortname,
          subpath,
          branch_name: "master",
          attributes: {},
        },
      ],
    };
    const response = await request(request_body);
    if (response.status === "success") {
      showToast(Level.info);
      history.go(-1);
    } else {
      showToast(Level.warn);
    }
  }

  function beforeUnload(event) {
    if (
      !isDeepEqual(removeEmpty(contentMeta), removeEmpty(oldContentMeta)) &&
      !isDeepEqual(removeEmpty(contentContent), removeEmpty(oldContent))
    ) {
      event.preventDefault();
      if (
        confirm("You have unsaved changes, do you want to leave ?") === false
      ) {
        return false;
      }
    }
  }

  let ticket_status = null;
  let ticket_action = null;
  let resolution = null;
  let comment;
  async function handleTicketSubmit(e) {
    e.preventDefault();
    const response = await progress_ticket(
      space_name,
      subpath,
      entry.shortname,
      ticket_action,
      resolution,
      comment
    );

    if (response.status === "success") {
      showToast(Level.info);
      window.location.reload();
    } else {
      showToast(Level.warn, response.error.message);
    }
  }
  const toggleModal = () => {
    isModalOpen = !isModalOpen;
    contentShortname = "";
  };

  let ticketPayload = null;
  async function get_ticket_payload() {
      ticketPayload = await get_payload(ResourceType.content, space_name, "workflows", entry.workflow_shortname)
      return ticketPayload;
  }

  let ticketStates = [];
  $:{
      if (ticketPayload){
        ticketStates = ticketPayload.states.filter((e) => e.state === entry.state)[0]?.next;
     }
  }

  let ticketResolutions = [];
  $:{
      if (ticketStates.length){
          ticketResolutions = ticketPayload.states.filter((e) => e.state === ticket_status)[0]?.resolutions ?? [];
      }
  }

  $: {
      ticket_action = ticketStates?.filter((e) => e.state === ticket_status)[0]?.action ?? null;
  }

  $: {
      if (ticket_status){
          resolution = null;
      }
  }

</script>

<svelte:window on:beforeunload={beforeUnload} />

<Modal isOpen={isModalOpen} toggle={toggleModal} size={"lg"}>
  <ModalHeader toggle={toggleModal} />
  <Form on:submit={async (e) => await handleSubmit(e)}>
    <ModalBody>
      <FormGroup>
        {#if modalFlag === "create"}
          <Label class="mt-3">Schema</Label>
          <Input bind:value={selectedSchema} type="select">
            <option value={""}>{"None"}</option>
            {#await query( { space_name, type: QueryType.search, subpath: "/schema", search: "", retrieve_json_payload: true, limit: 99 } ) then schemas}
              {#each schemas.records.map((e) => e.shortname) as schema}
                <option value={schema}>{schema}</option>
              {/each}
            {/await}
          </Input>
        {/if}
        {#if entryType === "content" && modalFlag === "create"}
          <Label class="mt-3">Shortname</Label>
          <Input placeholder="Shortname..." bind:value={contentShortname} />
          <hr />

          <Label class="mt-3">Content</Label>
          <JSONEditor
            onRenderMenu={handleRenderMenu}
            mode={Mode.text}
            bind:content={entryContent} />
          <!-- onChange={handleChange}
                {validator} -->

          <hr />

          <!-- <Label>Schema</Label>
              <ContentJsonEditor
                bind:self={refJsonEditor}
                content={contentSchema}
                readOnly={true}
                mode={Mode.tree}
              /> -->
        {/if}
        {#if entryType === "folder"}
          <Label class="mt-3">Shortname</Label>
          <Input
            placeholder="Shortname..."
            bind:value={contentShortname}
            required
          />
          {#if modalFlag === "update"}
            <Label class="mt-3">Content</Label>
          {/if}
        {/if}
      </FormGroup>
    </ModalBody>
    <ModalFooter>
      <Button
        type="button"
        color="secondary"
        on:click={() => {
          isModalOpen = false;
          contentShortname = "";
        }}>cancel</Button
      >
      <Button type="submit" color="primary">Submit</Button>
    </ModalFooter>
  </Form>
</Modal>

<div
  bind:clientHeight={header_height}
  class="pt-3 pb-2 px-2"
  transition:fade={{ delay: 25 }}
>
  <Nav class="w-100">
    <BreadCrumbLite
      {space_name}
      {subpath}
      {resource_type}
      {schema_name}
      shortname={entry.shortname}
    />
    <ButtonGroup size="sm" class="ms-auto align-items-center">
      <span class="ps-2 pe-1"> {$_("views")} </span>
      {#if resource_type === ResourceType.folder}
        <Button
          outline
          color="success"
          size="sm"
          class="justify-content-center text-center py-0 px-1"
          active={"list" === tab_option}
          title={$_("list")}
          on:click={() => (tab_option = "list")}
        >
          <Icon name="card-list" />
        </Button>
      {/if}

      <Button
        outline
        color="success"
        size="sm"
        class="justify-content-center text-center py-0 px-1"
        active={"view" === tab_option}
        title={$_("view")}
        on:click={() => (tab_option = "view")}
      >
        <Icon name="binoculars" />
      </Button>

      {#if canUpdate}
        <Button
          outline
          color="success"
          size="sm"
          class="justify-content-center text-center py-0 px-1"
          active={"edit_meta" === tab_option}
          title={$_("edit") + " meta"}
          on:click={() => (tab_option = "edit_meta")}
        >
          <Icon name="code-slash" />
        </Button>
        <Button
          outline
          color="success"
          size="sm"
          class="justify-content-center text-center py-0 px-1"
          active={"edit_content" === tab_option}
          title={$_("edit") + " payload"}
          on:click={() => (tab_option = "edit_content")}
        >
          <Icon name="pencil" />
        </Button>
        {#if schema}
          <Button
            outline
            color="success"
            size="sm"
            class="justify-content-center text-center py-0 px-1"
            active={"edit_content_form" === tab_option}
            title={$_("edit") + " payload"}
            on:click={() => (tab_option = "edit_content_form")}
          >
            <Icon name="pencil-square" />
          </Button>
        {/if}
      {/if}

      <Button
        outline
        color="success"
        size="sm"
        class="justify-content-center text-center py-0 px-1"
        active={"attachments" === tab_option}
        title={$_("attachments")}
        on:click={() => (tab_option = "attachments")}
      >
        <Icon name="paperclip" />
      </Button>
      <Button
        outline
        color="success"
        size="sm"
        class="justify-content-center text-center py-0 px-1"
        active={"history" === tab_option}
        title={$_("history")}
        on:click={() => (tab_option = "history")}
      >
        <Icon name="clock-history" />
      </Button>
    </ButtonGroup>
    <ButtonGroup size="sm" class="align-items-center">
      <span class="ps-2 pe-1"> {$_("actions")} </span>
      {#if canDelete}
        <Button
          outline
          color="success"
          size="sm"
          title={$_("delete")}
          on:click={handleDelete}
          class="justify-content-center text-center py-0 px-1"
        >
          <Icon name="trash" />
        </Button>
      {/if}
    </ButtonGroup>
    {#if resource_type === ResourceType.folder}
      <ButtonGroup>
        <Button
          outline
          color="success"
          size="sm"
          title={$_("create")}
          class="justify-contnet-center text-center py-0 px-1"
          on:click={() => {
            isModalOpen = true;
            entryType = "content";
          }}
          ><Icon name="file-plus" />
        </Button>
        <Button
          outline
          color="success"
          size="sm"
          title={$_("create")}
          class="justify-contnet-center text-center py-0 px-1"
          on:click={() => {
            isModalOpen = true;
            entryType = "folder";
          }}
          ><Icon name="folder-plus" />
        </Button>
      </ButtonGroup>
    {/if}
  </Nav>
</div>
<div
  class="px-1 tab-content"
  style="height: calc(100% - {header_height}px); overflow: hidden auto;"
  transition:fade={{ delay: 25 }}
>
  <div class="tab-pane" class:active={tab_option === "list"}>
    <ListView {space_name} {subpath} />
  </div>
  <div class="tab-pane" class:active={tab_option === "source"}>
    <!--JSONEditor json={entry} /-->
    <div
      class="px-1 pb-1 h-100"
      style="text-align: left; direction: ltr; overflow: hidden auto;"
    >
      <pre>
          {JSON.stringify(entry, undefined, 1)}
        </pre>
    </div>
  </div>
  <div class="tab-pane" class:active={tab_option === "view"}>
    <div
      class="px-1 pb-1 h-100"
      style="text-align: left; direction: ltr; overflow: hidden auto;"
    >
      <TabContent>
        <TabPane tabId="table" tab="Table" active><Table2Cols entry={{"Resource type": resource_type,...entry}} /></TabPane>
        <TabPane tabId="form" tab="Raw">
          <Prism code={entry} />
        </TabPane>
      </TabContent>
    </div>
  </div>
  <div class="tab-pane" class:active={tab_option === "edit_meta"}>
    {#if tab_option === "edit_meta"}
      <div
        class="px-1 pb-1 h-100"
        style="text-align: left; direction: ltr; overflow: hidden auto;"
      >
        <Form class="px-5 mb-5" on:submit={handleTicketSubmit}>
          {#await get_ticket_payload() then payload}
            <FormGroup>
              <Label>State</Label>
              <!-- on:change={handleInputChange} -->
              <Input
                class="w-25"
                type="select"
                name="status"
                placeholder="Status..."
                bind:value={ticket_status}
              >
                <option value={null}>Select next state</option>
                {#each ticketStates.map((e) => e) as e}
                  <option value={e.state} disabled={!e.roles.some((el) => userRoles.includes(el))}>{e.state}</option>
                {/each}
              </Input>
            </FormGroup>
            {#key ticket_status}
              {#if ticketResolutions.length !== 0}
                <FormGroup>
                  <Label>Resolution</Label>
                  <Input
                    class="w-25"
                    type="select"
                    name="resolution"
                    placeholder="Resolution..."
                    bind:value={resolution}
                  >
                    <option value={null}>Select resolution</option>
                    {#each ticketResolutions as resolution}
                      <option value={resolution}>{resolution}</option>
                    {/each}
                  </Input>
                </FormGroup>
              {/if}
            {/key}
          {/await}
          <FormGroup>
            <Label>Comment</Label>
            <!-- on:change={handleInputChange} -->
            <Input
              class="w-25"
              type="text"
              name="comment"
              placeholder="Comment..."
              bind:value={comment}
            />
          </FormGroup>
          <Button type="submit">Save</Button>
        </Form>

        <JSONEditor
          bind:content={contentMeta}
          onRenderMenu={handleRenderMenu}
          mode={Mode.text}
          bind:validator={validatorMeta}
        />
        {#if errorContent}
          <h3 class="mt-3">Error:</h3>
          <Prism bind:code={errorContent} />
        {/if}
      </div>
    {/if}
  </div>
  <div class="tab-pane" class:active={tab_option === "edit_content"}>
    {#if tab_option === "edit_content"}
      <JSONEditor
        bind:content={contentContent}
        bind:validator
        onRenderMenu={handleRenderMenu}
        mode={Mode.text}
      />
      {#if errorContent}
        <h3 class="mt-3">Error:</h3>
        <Prism bind:code={errorContent} />
      {/if}
    {/if}
  </div>
  {#if schema}
    <div class="tab-pane" class:active={tab_option === "edit_content_form"}>
      <div class="d-flex justify-content-end my-1">
        <Button on:click={handleSave}>Save</Button>
      </div>
      <div class="px-1 pb-1 h-100">
        <SchemaForm
          bind:ref={schemaFormRef}
          {schema}
          bind:data={contentContent.json}
        />
      </div>
    </div>
  {/if}
  <div class="tab-pane" class:active={tab_option === "history"}>
    {#key tab_option}
      <ListView
        {space_name}
        {subpath}
        type={QueryType.history}
        shortname={entry.shortname}
        is_clickable={false}
        columns={history_cols}
      />
    {/key}
    <!--History subpath="{entry.subpath}" shortname="{entry.shortname}" /-->
  </div>
  <div class="tab-pane" class:active={tab_option === "attachments"}>
    <Attachments
      {space_name}
      {subpath}
      parent_shortname={entry.shortname}
      attachments={Object.values(entry.attachments).flat(Infinity)}
    />
  </div>
</div>

<style>
  span {
    color: dimgrey;
  }
</style>
