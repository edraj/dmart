<script lang="ts">
  import HistoryListView from "./../HistoryListView.svelte";
  import Attachments from "../Attachments.svelte";
  import { onDestroy, onMount } from "svelte";
  import {
    QueryType,
    RequestType,
    ResourceType,
    ResponseEntry,
    Status,
    query,
    request,
    retrieve_entry,
    ContentType,
    upload_with_payload,
    csv, space,
  } from "@/dmart";
  import {
    Form,
    FormGroup,
    Button,
    Modal,
    ModalHeader,
    ModalBody,
    ModalFooter,
    Label,
    Input,
    Nav,
    ButtonGroup,
    Row,
    TabContent,
    TabPane
  } from "sveltestrap";
  import Icon from "../../Icon.svelte";
  import { _ } from "@/i18n";
  import ListView from "../ListView.svelte";
  import Prism from "@/components/Prism.svelte";
  import {
    JSONEditor,
    Mode,
    Validator,
    createAjvValidator,
  } from "svelte-jsoneditor";
  import { status_line } from "@/stores/management/status_line";
  import { authToken } from "@/stores/management/auth";
  import { timeAgo } from "@/utils/timeago";
  import { showToast, Level } from "@/utils/toast";
  import { faSave } from "@fortawesome/free-regular-svg-icons";
  import refresh_spaces from "@/stores/management/refresh_spaces";
  import { website } from "@/config";
  import HtmlEditor from "../editors/HtmlEditor.svelte";
  import MarkdownEditor from "../editors/MarkdownEditor.svelte";
  import { isDeepEqual, removeEmpty } from "@/utils/compare";
  import metaContentSchema from "@/validations/meta.content.json";
  import SchemaEditor, {
    transformToProperBodyRequest,
  } from "../editors/SchemaEditor.svelte";
  import checkAccess from "@/utils/checkAccess";
  import { fade } from "svelte/transition";
  import BreadCrumbLite from "../BreadCrumbLite.svelte";
  import { generateUUID } from "@/utils/uuid";
  import downloadFile from "@/utils/downloadFile";
  import {schemaVisualizationEncoder} from "@/utils/plantUML";
  import SchemaForm from "svelte-jsonschema-form";
  import {goto} from "@roxi/routify";
  // import { SchemaForm } from "svelte-schemaform"
  // import { SchemaForm } from "@restspace/svelte-schema-form";
  // import './assets/layout.css';
  // import './assets/basic-skin.css';

  let header_height: number;

  export let entry: ResponseEntry;

  export let space_name: string;
  export let subpath: string;
  export let resource_type: ResourceType;
  export let schema_name: string | undefined = null;
  export let refresh = {};

  const canUpdate = checkAccess("update", space_name, subpath, resource_type);
  const canDelete = checkAccess("delete", space_name, subpath, resource_type);

  let tab_option = resource_type === ResourceType.folder ? "list" : "view";
  let content = { json: entry, text: undefined };

  let contentMeta = { json: {}, text: undefined };
  let validatorMeta: Validator = createAjvValidator({
    schema: metaContentSchema,
  });
  let oldContentMeta = { json: {}, text: undefined };

  let contentContent: any = null;
  let validator: Validator = createAjvValidator({ schema: {} });
  let validatorContent: Validator = createAjvValidator({ schema: {} });
  let entryContent: any;

  const resourceTypes = [ResourceType.content];

  let ws = null;
  if ("websocket" in website)
    ws = new WebSocket(`${website.websocket}?token=${$authToken}`);

  function isOpen(ws: any) {
    return ws != null && ws.readyState === ws.OPEN;
  }

  const managementEntities = [
    "management/users",
    "management/roles",
    "management/permissions",
    "management/groups",
    "management/workflows",
    "/schema",
  ];

  let selectedSchemaContent: any = {};
  let selectedSchemaData: any = {};

  async function checkWorkflowsSubpath() {
    const chk = await retrieve_entry(
      ResourceType.folder,
      space_name,
      "/",
      "workflows",
      true,
      false,
      true
    );
    if (chk) {
      resourceTypes.push(ResourceType.ticket);
    }
  }

  let isNeedRefresh = false;
  onMount(async () => {
    const cpy = structuredClone(entry);
    if (entry?.payload?.content_type === "json") {
      if (contentContent === null) {
        contentContent = { json: {}, text: undefined };
      }
      contentContent.json = cpy?.payload?.body ?? {};
      contentContent = structuredClone(contentContent);
    }
    else {
      contentContent = cpy?.payload?.body;
    }
    delete cpy?.payload?.body;
    delete cpy?.attachments;

    contentMeta.json = cpy;
    contentMeta = structuredClone(contentMeta);
    oldContentMeta = structuredClone(contentMeta);

    if (ws != null) {
      ws.onopen = () => {
        ws.send(
          JSON.stringify({
            type: "notification_subscription",
            space_name: space_name,
            subpath: subpath,
          })
        );
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event?.data ?? "");
        if (data?.message?.title) {
          isNeedRefresh = true;
        }
      };
    }

    await checkWorkflowsSubpath();

    if (entry?.payload?.schema_shortname) {
        await get_schema();
    }
  });

  onDestroy(() => {
    status_line.set("");

    if (isOpen(ws)) {
      ws.send(JSON.stringify({ type: "notification_unsubscribe" }));
    }
    if (ws != null) ws.close();
  });
  status_line.set(
    `<small>Last updated: <strong>${timeAgo(
      new Date(entry.updated_at)
    )}</strong><br/>Attachments: <strong>${
      Object.keys(entry.attachments).length
    }</strong></small>`
  );

  let errorContent = null;

  let schemaFormRef;
  async function handleSave(e: Event) {
    e.preventDefault();
    // if (!isSchemaValidated) {
    //   alert("The content does is not validated agains the schema");
    //   return;
    // }
    errorContent = null;

    const x = contentMeta.json
      ? structuredClone(contentMeta.json)
      : JSON.parse(contentMeta.text);

    let data: any = structuredClone(x);
    if (entry?.payload) {
      if (entry?.payload?.content_type === "json") {
        const y = contentContent.json
          ? structuredClone(contentContent.json)
          : JSON.parse(contentContent.text);
        if (data.payload) {
          data.payload.body = y;
        }
      } else {
        data.payload.body = contentContent;
      }
    }

    if (resource_type === ResourceType.folder) {
      const arr = subpath.split("/");
      arr[arr.length - 1] = "";
      subpath = arr.join("/");
    }
    subpath = subpath == "__root__" || subpath == "" ? "/" : subpath;

    const request_data = {
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
    };

    const response = await request(request_data);
    if (response.status == Status.success) {
      showToast(Level.info);
      oldContentMeta = structuredClone(contentMeta);

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
        if (response.status == Status.success) {
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
    } else {
      errorContent = response;
      showToast(Level.warn);
    }
  }

  function handleRenderMenu(items: any, _context: any) {
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

  function cleanUpSchema(obj: Object) {
    for (let prop in obj) {
      if (prop === "comment") delete obj[prop];
      else if (typeof obj[prop] === "object") cleanUpSchema(obj[prop]);
    }
  }

  let schema = null;
  async function get_schema() {
    if (entry.payload && entry.payload.schema_shortname) {
      try {
        const schema_data: ResponseEntry | null = await retrieve_entry(
          ResourceType.schema,
          space_name,
          "/schema",
          entry.payload.schema_shortname,
          true,
          false
        );
        if (schema_data === null){
            schema = {};
            return;
        }
        if (schema_data?.payload?.body) {
          schema = schema_data.payload.body;
          cleanUpSchema(schema.properties);
          validator = createAjvValidator({ schema });
        } else {
          schema = {};
        }
      }
      catch (x) {
        showToast(Level.warn, "Schema loading failed");
        schema = {};
      }
    }
    else {
      schema = {};
    }
  }

  let isModalOpen = false;
  let modalFlag = "create";
  let entryType = "folder";
  let contentShortname = "";
  let workflowShortname = "";
  let selectedSchema = subpath === "workflows" ? "workflow" : "";
  let selectedContentType = ContentType.json;
  let new_resource_type: ResourceType = resolveResourceType(
    ResourceType.content
  );
  let payloadFiles: FileList;

  let itemsSchemaContent: any = [
    {
      id: generateUUID(),
      name: "root",
      type: "object",
      title: "title",
      description: "",
    },
  ];

  function resolveResourceType(resourceType: ResourceType) {
    const fullSubpath = `${space_name}/${subpath}`;
    switch (fullSubpath) {
      case "management/users":
        return ResourceType.user;
      case "management/roles":
        return ResourceType.role;
      case "management/permissions":
        return ResourceType.permission;
      case "management/groups":
        return ResourceType.group;
    }
    return fullSubpath.endsWith("/schema") ? ResourceType.schema : resourceType;
  }

  let schemaContent = {json:{}, text: undefined};
  let isSchemaEntryInForm = true;
  let isContentEntryInForm = true;
  async function handleSubmit(event: Event) {
    event.preventDefault();

    let response: any;
    let request_body: any = {};
    if (new_resource_type === "schema") {
        let body = null;
      if (isSchemaEntryInForm){
          body = content.json
              ? structuredClone(content.json)
              : JSON.parse(content.text);
          body = transformToProperBodyRequest(body);
          body = body[0];
          delete body.name;
      } else {
          body = schemaContent.json
              ? structuredClone(schemaContent.json)
              : JSON.parse(schemaContent.text);
          schemaContent = {json:{}, text: undefined};
      }

      request_body = {
        space_name,
        request_type: RequestType.create,
        records: [
          {
            resource_type: ResourceType.schema,
            shortname: contentShortname === "" ? "auto" : contentShortname,
            subpath,
            attributes: {
              is_active: true,
              payload: {
                content_type: "json",
                schema_shortname: "meta_schema",
                body,
              },
            },
          },
        ],
      };
      response = await request(request_body);
    }
    else if (entryType === "content") {
      if (
        [null, "json", "text", "html", "markdown"].includes(selectedContentType)
      ) {
        let body: any;
        if (selectedContentType === "json") {
            if (isContentEntryInForm){
                if (
                    selectedSchemaContent != null &&
                    selectedSchemaData &&
                    Object.keys(selectedSchemaData).length !== 0
                ) {
                    if (!schemaFormRef.reportValidity()) {
                        return;
                    }
                    body = selectedSchemaData;
                }
            }
            else {
                body = entryContent.json
                    ? structuredClone(entryContent.json)
                    : JSON.parse(entryContent.text);
            }
        }
        else {
          body = entryContent;
        }

        request_body = {
          space_name,
          request_type: RequestType.create,
          records: [
            {
              resource_type: new_resource_type,
              shortname: contentShortname === "" ? "auto" : contentShortname,
              subpath,
              attributes: {
                ...request_body,
                workflow_shortname: workflowShortname,
                is_active: true,
              },
            },
          ],
        };
        if (new_resource_type === "ticket") {
          request_body.records[0].attributes.workflow_shortname =
            workflowShortname;
          selectedContentType = ContentType.json;
        }
        if (selectedContentType !== null) {
          const schema_shortname =
            subpath === "workflows"
              ? "workflow"
              : selectedSchema
              ? selectedSchema
              : "";
          const content_type = selectedContentType
            ? selectedContentType
            : "json";
          request_body.records[0].attributes.payload = {
            content_type,
            schema_shortname,
            body,
          };
        }
        response = await request(request_body);
      } else if (
        ["image", "python", "pdf", "audio", "video"].includes(
          selectedContentType
        )
      ) {
        response = await upload_with_payload(
          space_name,
          subpath,
          ResourceType[new_resource_type],
          contentShortname === "" ? "auto" : contentShortname,
          payloadFiles[0]
        );
      }
    }
    else if (entryType === "folder") {
        let body = {}
      if (selectedSchema ===  "folder_rendering"){
          body["index_attributes"] = [];
      }
      request_body = {
        space_name,
        request_type: RequestType.create,
        records: [
          {
            resource_type: ResourceType.folder,
            shortname: contentShortname === "" ? "auto" : contentShortname,
            subpath,
            attributes: {
              payload: {
                  content_type: "json",
                  schema_shortname: selectedSchema,
                  body
              },
              is_active: true,
            },
          },
        ],
      };
      response = await request(request_body);
    }

    if (response.status === "success") {
      showToast(Level.info);
      contentShortname = "";
      isModalOpen = false;
      refresh = !refresh;
    }
    else {
      showToast(Level.warn);
    }
  }

  async function handleDelete() {
    if (
      confirm(`Are you sure want to delete ${entry.shortname} entry`) === false
    ) {
      return;
    }

    let targetSubpath: string;
    if (resource_type === ResourceType.folder) {
      const arr = subpath.split("/");
      arr[arr.length - 1] = "";
      targetSubpath = arr.join("/");
    } else {
      targetSubpath = subpath;
    }

    let response: any = {};
    if (targetSubpath !== "/"){
      const request_body = {
        space_name,
        request_type: RequestType.delete,
        records: [
          {
            resource_type,
            shortname: entry.shortname,
            subpath: targetSubpath || "/",
            branch_name: "master",
            attributes: {},
          },
        ],
      };
      response = await request(request_body);
    } else {
      const request_body = {
          space_name,
          request_type: RequestType.delete,
          records: [
              {
                  resource_type: ResourceType.space,
                  subpath: "/",
                  shortname: entry.shortname,
                  attributes: {},
              },
          ],
      };
      response = await space(request_body);
    }

    if (response?.status === "success") {
      showToast(Level.info);
      // await spaces.refresh();
      refresh_spaces.refresh();
      history.go(-1);
    } else {
      showToast(Level.warn);
    }
  }

  function beforeUnload(event) {
    if (!isDeepEqual(removeEmpty(contentMeta), removeEmpty(oldContentMeta))) {
      event.preventDefault();
      if (
        confirm("You have unsaved changes, do you want to leave ?") === false
      ) {
        return false;
      }
    }
  }

  $: {
    if (selectedContentType === "json") {
      entryContent = { json: {} || {}, text: undefined };
    } else {
      entryContent = "";
    }
  }

  async function handleDownload() {
    const body = {
      space_name,
      subpath,
      type: "search",
      search: "",
      retrieve_json_payload: true,
      limit: 1000,
      branch_name: "master",
      filter_schema_names: [],
    };
    const data = await csv(body);
    downloadFile(data, `${space_name}/${subpath}.csv`, "text/csv");
  }

  let oldSelectedSchema = "old";
  let schemaForm: SchemaForm;
  let uischema = {};
  $: {
    if (oldSelectedSchema !== selectedSchema && selectedSchema !== '') {
      (async () => {
        const _selectedSchemaContent = await retrieve_entry(
          ResourceType.schema,
          space_name,
          "schema",
          selectedSchema,
          true
        );
        selectedSchemaContent = _selectedSchemaContent?.payload?.body ?? {};
        delete selectedSchemaContent.required;
        cleanUpSchema(selectedSchemaContent.properties);
        validatorContent = createAjvValidator({ schema:  selectedSchemaContent });
        oldSelectedSchema = selectedSchema;
      })();
    }
  }

  const modalToggle = () => {
    isModalOpen = !isModalOpen;
    contentShortname = "";
  };

  function setSchemaItems(schemas): Array<string> {
    if (schemas === null){
        return [];
    }
    const _schemas = schemas.records.map((e) => e.shortname);
    if (entryType === "folder"){
      return _schemas.filter((e) => ["meta_schema", "folder_rendering"].includes(e));
    } else {
      return _schemas.filter((e) => !["meta_schema", "folder_rendering"].includes(e));
    }
  }
</script>

<svelte:window on:beforeunload={beforeUnload} />

<Modal
  isOpen={isModalOpen}
  toggle={modalToggle}
  size={new_resource_type === "schema" ? "xl" : "lg"}
>
  <ModalHeader toggle={modalToggle}>
    Creating an {new_resource_type} under
    <span class="text-success">{space_name}</span>/<span class="text-primary">{subpath}</span>
  </ModalHeader>
  <Form on:submit={async (e) => await handleSubmit(e)}>
    <ModalBody>
      <FormGroup>
        {#if modalFlag === "create"}
          {#if entryType !== "folder"}
            {#if !managementEntities.some( (m) => `${space_name}/${subpath}`.endsWith(m) )}
              <Label for="resource_type" class="mt-3">Resource type</Label>
              <Input
                id="resource_type"
                bind:value={new_resource_type}
                type="select"
              >
                {#each resourceTypes as type}
                  <option value={type}>{type}</option>
                {/each}
              </Input>
            {/if}
            {#if new_resource_type !== "schema"}
              {#if !managementEntities.some( (m) => `${space_name}/${subpath}`.endsWith(m) ) && new_resource_type !== "ticket"}
                <Label for="content_type" class="mt-3">Content type</Label>
                <Input
                  id="content_type"
                  bind:value={selectedContentType}
                  type="select"
                >
                  <option value={null}>{"None"}</option>
                  {#each Object.values(ContentType) as type}
                    <option value={type}>{type}</option>
                  {/each}
                </Input>
              {/if}
              {#if new_resource_type === "ticket"}
                <Label class="mt-3">Workflow Shortname</Label>
                <Input
                  placeholder="Shortname..."
                  bind:value={workflowShortname}
                />
              {/if}
            {/if}
          {/if}
        {/if}

        {#if subpath !== "workflows"}
          <Label class="mt-3">Schema</Label>
          <Input bind:value={selectedSchema} type="select">
            <option value={null}>{"None"}</option>
            {#await query( { space_name, type: QueryType.search, subpath: "/schema", search: "", retrieve_json_payload: true, limit: 99 } ) then schemas}
              {#each setSchemaItems(schemas) as schema}
                <option value={schema}>{schema}</option>
              {/each}
            {/await}
          </Input>
        {/if}

        <Label class="mt-3">Shortname</Label>
        <Input
          placeholder="Shortname..."
          bind:value={contentShortname}
          required
        />
        <hr />
        {#if modalFlag === "create"}
          {#if new_resource_type === "schema"}
            <TabContent on:tab={(e) => (isSchemaEntryInForm = e.detail==="form")}>
              <TabPane tabId="form" tab="Forms" active>
                <SchemaEditor bind:content bind:items={itemsSchemaContent} />
              </TabPane>
              <TabPane tabId="editor" tab="Editor">
                <JSONEditor
                  mode={Mode.text}
                  bind:content={schemaContent}
                />
              </TabPane>
            </TabContent>
            <Row>
              {#if errorContent}
                <h3 class="mt-3">Error:</h3>
                <Prism bind:code={errorContent} />
              {/if}
            </Row>
          {:else if selectedContentType}
            {#if ["image", "python", "pdf", "audio", "video"].includes(selectedContentType)}
              <Label class="mt-3">Payload</Label>
              <Input
                accept="image/png, image/jpeg"
                bind:files={payloadFiles}
                type="file"
              />
            {/if}
            {#if selectedContentType === "json"}
                <Label class="mt-3">Payload</Label>
                <TabContent on:tab={(e) => (isContentEntryInForm = e.detail==="form")}>
                  {#if selectedSchemaContent && Object.keys(selectedSchemaContent).length !== 0}
                  <TabPane tabId="form" tab="Form" active>
                    <SchemaForm
                      bind:ref={schemaFormRef}
                      schema={selectedSchemaContent}
                      bind:data={selectedSchemaData}
                    />
                  </TabPane>
                 {/if}
                  <TabPane tabId="editor" tab="Editor">
                    <JSONEditor
                      mode={Mode.text}
                      bind:content={entryContent}
                      bind:validator={validatorContent}
                    />
                  </TabPane>
                </TabContent>
              {/if}
            {#if selectedContentType === "text"}
              <Label class="mt-3">Payload</Label>
              <Input type="textarea" bind:value={entryContent} />
            {/if}
            {#if selectedContentType === "html"}
              <Label class="mt-3">Payload</Label>
              <HtmlEditor bind:content={entryContent} />
            {/if}
            {#if selectedContentType === "markdown"}
              <Label class="mt-3">Payload</Label>
              <MarkdownEditor bind:content={entryContent} />
            {/if}
          {/if}
          <hr />
        {/if}
        {#if entryType === "folder"}
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
        }}
        >cancel
      </Button>
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
        {#if entry.payload}
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

        {#if resource_type === ResourceType.schema}
          <Button
            outline
            color="success"
            size="sm"
            class="justify-content-center text-center py-0 px-1"
            active={"visualization" === tab_option}
            title={$_("edit") + " payload"}
            on:click={() => (tab_option = "visualization")}
          >
            <Icon name="diagram-3" />
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
      <Button
        outline
        color="success"
        size="sm"
        title={$_("download")}
        on:click={handleDownload}
        class="justify-content-center text-center py-0 px-1"
      >
        <Icon name="cloud-download" />
      </Button>
    </ButtonGroup>
    {#if resource_type === ResourceType.folder}
      <ButtonGroup>
        {#if subpath !== "health_check"}
          <Button
            outline
            color="success"
            size="sm"
            title={$_("create_entry")}
            class="justify-contnet-center text-center py-0 px-1"
            on:click={() => {
              entryType = "content";
              isModalOpen = true;
            }}
          >
            <Icon name="file-plus" />
          </Button>
          {#if !managementEntities.some( (m) => `${space_name}/${subpath}`.endsWith(m) )}
            <Button
              outline
              color="success"
              size="sm"
              title={$_("create_folder")}
              class="justify-contnet-center text-center py-0 px-1"
              on:click={() => {
                entryType = "folder";
                new_resource_type = ResourceType.folder;
                isModalOpen = true;
              }}
            >
              <Icon name="folder-plus" />
            </Button>
          {/if}
        {/if}
        <Button
          outline={!isNeedRefresh}
          color={isNeedRefresh ? "danger" : "success"}
          size="sm"
          title={$_("refresh")}
          class="justify-contnet-center text-center py-0 px-1"
          on:click={() => {
            refresh = !refresh;
          }}
        >
          <Icon name="arrow-clockwise" />
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
      <Prism code={entry} />
    </div>
  </div>
  <div class="tab-pane" class:active={tab_option === "edit_meta"}>
    {#if tab_option === "edit_meta"}
      <div
        class="px-1 pb-1 h-100"
        style="text-align: left; direction: ltr; overflow: hidden auto;"
      >
        <JSONEditor
          mode={Mode.text}
          bind:content={contentMeta}
          bind:validator={validatorMeta}
          onRenderMenu={handleRenderMenu}
        />
        {#if errorContent}
          <h3 class="mt-3">Error:</h3>
          <Prism bind:code={errorContent} />
        {/if}
      </div>
    {/if}
  </div>
  {#if entry.payload}
    <div class="tab-pane" class:active={tab_option === "edit_content"}>
      <div
        class="px-1 pb-1 h-100"
        style="text-align: left; direction: ltr; overflow: hidden auto;"
      >
        {#if entry.payload.content_type === "image"}
          {#if entry?.payload?.body.endsWith(".wsq")}
            <a
              target="_blank"
              download={entry?.payload?.body}
              href={`${website.backend}/managed/payload/media/${space_name}/${subpath}/${entry?.payload?.body}`}
              >{entry?.payload?.body}</a
            >
          {:else}
            <img
              src={`${website.backend}/managed/payload/media/${space_name}/${subpath}/${entry?.payload?.body}`}
              alt=""
              class="mw-100 border"
            />{/if}
        {/if}
        {#if entry.payload.content_type === "audio"}
          <audio
            controls
            src={`${website.backend}/managed/payload/content/${space_name}/${subpath}/${entry?.payload?.body}`}
          >
            <track kind="captions" />
          </audio>
        {/if}
        {#if entry.payload.content_type === "video"}
          <video
            controls
            src={`${website.backend}/managed/payload/content/${space_name}/${subpath}/${entry?.payload?.body}`}
          >
            <track kind="captions" />
          </video>
        {/if}
        {#if entry.payload.content_type === "pdf"}
          <object
            title=""
            class="h-100 w-100 embed-responsive-item"
            type="application/pdf"
            style="height: 100vh;"
            data={`${website.backend}/managed/payload/content/${space_name}/${subpath}/${entry?.payload?.body}`}
          >
            <p>For some reason PDF is not rendered here properly.</p>
          </object>
        {/if}
        {#if entry.payload.content_type === "markdown"}
          <div class="d-flex justify-content-end">
            <Button on:click={handleSave}>Save</Button>
          </div>
          <MarkdownEditor bind:content={contentContent} />
        {/if}
        {#if entry.payload.content_type === "html"}
          <div class="d-flex justify-content-end">
            <Button on:click={handleSave}>Save</Button>
          </div>
          <HtmlEditor bind:content={contentContent} />
        {/if}
        {#if entry.payload.content_type === "text"}
          <div class="d-flex justify-content-end">
            <Button on:click={handleSave}>Save</Button>
          </div>
          <Input class="mt-3" type="textarea" bind:value={contentContent} />
        {/if}
        {#if entry.payload.content_type === "json" && typeof contentContent === "object" && contentContent !== null}
          <JSONEditor
            mode={Mode.text}
            bind:content={contentContent}
            bind:validator
            onRenderMenu={handleRenderMenu}
          />
        {/if}

        {#if errorContent}
          <h3 class="mt-3">Error:</h3>
          <Prism bind:code={errorContent} />
        {/if}
      </div>
    </div>
    {#if schema && contentContent?.json}
      <div class="tab-pane" class:active={tab_option === "edit_content_form"}>
        <div class="d-flex justify-content-end my-1">
          <Button on:click={handleSave}>Save</Button>
        </div>
        <div class="px-1 pb-1 h-100">
<!--          <SchemaForm-->
<!--            bind:ref={schemaFormRef}-->
<!--            {schema}-->
<!--            bind:data={contentContent.json}-->
<!--          />-->
        </div>
      </div>
    {/if}
  {/if}
  {#if resource_type === ResourceType.schema}
    <div class="tab-pane" class:active={tab_option === "visualization"}>
      <div
        class="px-1 pb-1 h-100"
        style="text-align: left; direction: ltr; overflow: hidden auto;"
      >
        <div class="preview">
          <a
            href={"https://www.plantuml.com/plantuml/svg/" +
              schemaVisualizationEncoder(entry)}
            download="{entry.shortname}.svg"
          >
            <img
              src={"https://www.plantuml.com/plantuml/svg/" +
                schemaVisualizationEncoder(entry)}
              alt={entry.shortname}
            />
          </a>
        </div>
      </div>
    </div>
  {/if}
  <div class="tab-pane" class:active={tab_option === "history"}>
    {#key tab_option}
      {#if tab_option === "history"}
        <HistoryListView
          {space_name}
          {subpath}
          type={QueryType.history}
          shortname={entry.shortname}
        />
      {/if}
    {/key}
    <!--History subpath="{entry.subpath}" shortname="{entry.shortname}" /-->
  </div>
  <div class="tab-pane" class:active={tab_option === "attachments"}>
    <Attachments
      {space_name}
      {subpath}
      parent_shortname={entry.shortname}
      attachments={Object.values(entry.attachments)}
    />
  </div>
</div>

<style>
  span {
    color: dimgrey;
  }

  :global(.X) {
    transform: translate(-50%, -15%) !important;
    left: 50%;
    max-width: 90%;
  }
</style>
