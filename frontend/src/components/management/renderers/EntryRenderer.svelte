<script lang="ts">
  import {onDestroy, onMount} from "svelte";
  import {
      check_existing,
      ContentType,
      create_user,
      csv,
      passwordRegExp,
      passwordWrongExp,
      query,
      QueryType,
      request,
      RequestType,
      ResourceType,
      ResponseEntry,
      retrieve_entry,
      space,
      Status,
      upload_with_payload,
  } from "@/dmart";
  import {
      Alert,
      Button,
      ButtonGroup,
      Form,
      FormGroup,
      Input,
      Label,
      Modal,
      ModalBody,
      ModalFooter,
      ModalHeader,
      Nav,
      Row,
      TabContent,
      TabPane
  } from "sveltestrap";
  import Icon from "../../Icon.svelte";
  import {_} from "@/i18n";
  import ListView from "../ListView.svelte";
  import Prism from "@/components/Prism.svelte";
  import {createAjvValidator, JSONEditor, Mode, Validator,} from "svelte-jsoneditor";
  import {status_line} from "@/stores/management/status_line";
  import {authToken} from "@/stores/management/auth";
  import {timeAgo} from "@/utils/timeago";
  import {Level, showToast} from "@/utils/toast";
  import {faSave} from "@fortawesome/free-regular-svg-icons";
  import refresh_spaces from "@/stores/management/refresh_spaces";
  import {website} from "@/config";
  import HtmlEditor from "../editors/HtmlEditor.svelte";
  import MarkdownEditor from "../editors/MarkdownEditor.svelte";
  import {isDeepEqual, removeEmpty} from "@/utils/compare";
  import metaContentSchema from "@/validations/meta.content.json";
  import SchemaEditor from "@/components/management/editors/SchemaEditor.svelte";
  import checkAccess from "@/utils/checkAccess";
  import {fade} from "svelte/transition";
  import BreadCrumbLite from "../BreadCrumbLite.svelte";
  import downloadFile from "@/utils/downloadFile";
  import {schemaVisualizationEncoder} from "@/utils/plantUML";
  import SchemaForm from "svelte-jsonschema-form";
  import Table2Cols from "@/components/management/Table2Cols.svelte";
  import Attachments from "@/components/management/Attachments.svelte";
  import HistoryListView from "@/components/management/HistoryListView.svelte";
  import {marked} from "marked";
  import {cleanUpSchema, generateObjectFromSchema} from "@/utils/renderer/rendererUtils";
  import TranslationEditor from "@/components/management/editors/TranslationEditor.svelte";
  import ConfigEditor from "@/components/management/editors/ConfigEditor.svelte";
  import {metadata} from "@/stores/management/metadata";
  import metaUserSchema from "@/validations/meta.user.json";
  import metaRoleSchema from "@/validations/meta.role.json";
  import metaPermissionSchema from "@/validations/meta.permission.json";

  let header_height: number;

  export let entry: ResponseEntry;
  export let space_name: string;
  export let subpath: string;
  export let resource_type: ResourceType;
  export let schema_name: string | undefined = null;
  export let refresh = {};

  const canUpdate = checkAccess("update", space_name, subpath, resource_type);
  const canDelete = checkAccess("delete", space_name, subpath, resource_type) && !(
      space_name==="management" && subpath==="/"
  );

  let tab_option = (resource_type === ResourceType.folder || resource_type === ResourceType.space) ? "list" : "view";
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

  let resourceTypes = [ResourceType.content];

  let ws = null;


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
  let selectedSchemaData: any = {json:{}, text: undefined};

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
    if (entry?.payload?.body?.content_resource_types){
        const content_resource_types = entry?.payload?.body?.content_resource_types
        resourceTypes = resourceTypes.filter((e) => content_resource_types.includes(e));
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

    if (!!entry?.payload?.body?.stream) {

      if ("websocket" in website) {
          ws = new WebSocket(`${website.websocket}?token=${$authToken}`);
      }

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

    status_line.set(
        `<small>Last updated: <strong>${timeAgo(
            new Date(entry.updated_at)
        )}</strong><br/>Attachments: <strong>${
            Object.keys(entry.attachments).length
        }</strong></small>`
    );
  });

  onDestroy(() => {
    status_line.set("");

    if (isOpen(ws)) {
      ws.send(JSON.stringify({ type: "notification_unsubscribe" }));
    }
    if (ws != null) ws.close();
  });


  let errorContent = null;
  let schemaFormRefModal;
  let schemaFormRefContent;
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
        if (tab_option === "edit_content_form"){
            if (schemaFormRefContent && !schemaFormRefContent.reportValidity()) {
                return;
            }
        }
        const y = contentContent.json
          ? structuredClone(contentContent.json)
          : JSON.parse(contentContent.text);

          if (new_resource_type === "schema") {
              if (isSchemaEntryInForm){
                  delete y.name;
              }
          }

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
    subpath = subpath === "__root__" || subpath === "" ? "/" : subpath;

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

    let response;
    if (resource_type === ResourceType.space){
        request_data.request_type = RequestType.update;
        request_data.records[0].resource_type = ResourceType.space;
        response = await space(request_data);
    }
    else {
        response = await request(request_data);
    }

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
          window.location.reload();
        } else {
          errorContent = response;
          showToast(Level.warn);
        }
      }
      window.location.reload();
    }
    else {
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
      let body = schemaContent.json
          ? structuredClone(schemaContent.json)
          : JSON.parse(schemaContent.text);

      if (isSchemaEntryInForm){
          delete body.name;
      }

      if (body.payload){
          body.payload = {
              content_type: "json",
              schema_shortname: "meta_schema",
              body: body.payload,
          };
      }
      request_body = {
        space_name,
        request_type: RequestType.create,
        records: [
          {
            resource_type: ResourceType.schema,
            shortname: contentShortname === "" ? "auto" : contentShortname,
            subpath,
            attributes: body,
          },
        ],
      };
      response = await request(request_body);
    }
    else if (new_resource_type === ResourceType.user){
        if (!schemaFormRefModal.reportValidity()) {
            return;
        }

        let body;
        if (isContentEntryInForm){
            body = selectedSchemaData.json
                ? structuredClone(selectedSchemaData.json)
                : JSON.parse(selectedSchemaData.text);
            body = {
                attributes: body
            }
        } else {
            body = entryContent.json
                ? structuredClone(entryContent.json)
                : JSON.parse(entryContent.text);
        }


        if (body.attributes?.password===null){
            showToast(Level.warn, passwordWrongExp);
            return;
        }

        const shortnameStatus: any = await check_existing("shortname",contentShortname);
        if (!shortnameStatus.attributes.unique){
            showToast(Level.warn,"Shortname already exists!");
            return;
        }

        if (body.attributes.email) {
            const emailStatus: any = await check_existing("email", body.attributes.email);
            if (!emailStatus.attributes.unique) {
                showToast(Level.warn, "Email already exists!");
                return;
            }
        } else {
            delete body.attributes.email;
        }

        if (body.attributes.msisdn) {
            const msisdnStatus: any = await check_existing("msisdn", body.attributes.msisdn);
            if (!msisdnStatus.attributes.unique) {
                showToast(Level.warn, "MSISDN already exists!");
                return;
            }
        } else {
            delete body.attributes.msisdn;
        }

        if (!body.shortname){
            body.shortname = contentShortname;
        }
        if (body.attributes.is_active === undefined){
            body.attributes.is_active = true;
        }
        if (body.attributes.invitation === undefined){
            body.attributes.invitation = "sysadmin";
        }

        body.subpath = "users";
        body.resource_type = "user";

        response = await create_user(body);

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
                    selectedSchemaData.json
                ) {
                   if (!schemaFormRefModal.reportValidity()) {
                        return;
                   }
                   body = selectedSchemaData.json;
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

        if (new_resource_type === ResourceType.role || new_resource_type === ResourceType.permission){
            request_body = {
                space_name,
                request_type: RequestType.create,
                records: [
                    {
                        resource_type: new_resource_type,
                        shortname: contentShortname === "" ? "auto" : contentShortname,
                        subpath,
                        attributes: body,
                    },
                ],
            };
        }
        else {
          if (workflowShortname){
              request_body = {...request_body, workflow_shortname:workflowShortname}
          }

          request_body = {
            space_name,
            request_type: RequestType.create,
            records: [
              {
                resource_type: new_resource_type,
                shortname: contentShortname === "" ? "auto" : contentShortname,
                subpath,
                attributes: request_body,
              },
            ],
          };
        }
        if (new_resource_type === ResourceType.ticket) {
          request_body.records[0].attributes.workflow_shortname =
            workflowShortname;
          selectedContentType = ContentType.json;
        }
        if (selectedContentType !== null
            && new_resource_type !== ResourceType.role
            && new_resource_type !== ResourceType.permission
        ) {
          request_body.records[0].attributes = body;
          if (body.payload){
              body.payload = {
                  content_type: "json",
                  schema_shortname: selectedSchema,
                  body: body.payload,
              };
          }
        }
        response = await request(request_body);
      }
      else if (
        ["image", "python", "pdf", "audio", "video"].includes(
          selectedContentType
        )
      ) {
        response = await upload_with_payload(
          space_name,
          subpath,
          ResourceType[new_resource_type],
          null,
          contentShortname === "" ? "auto" : contentShortname,
          payloadFiles[0]
        );
      }
    }
    else if (entryType === "folder") {
      let body: any = {}
      if (isContentEntryInForm){
          body = selectedSchemaData.json
              ? structuredClone(selectedSchemaData.json)
              : JSON.parse(selectedSchemaData.text);
      } else {
          body = entryContent.json
              ? structuredClone(entryContent.json)
              : JSON.parse(entryContent.text);
      }
      if (selectedSchema === "folder_rendering"){
          body["index_attributes"] = [];
      }

      body = {
        ...body,
        payload: {
          content_type: "json",
          schema_shortname: selectedSchema,
          body: body.payload ?? {}
        }
      };

      request_body = {
        space_name,
        request_type: RequestType.create,
        records: [
          {
            resource_type: ResourceType.folder,
            shortname: contentShortname === "" ? "auto" : contentShortname,
            subpath,
            attributes: body,
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
    if (targetSubpath !== "/" || entry.payload){
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
  let baseEntryContent;
  $: {
    if (selectedContentType === "json") {
      entryContent = { json: {} || {}, text: undefined };
    } else {
      entryContent = "";
    }
  }
  $: {
      if (new_resource_type === ResourceType.user){
          const meta = metaUserSchema;
          delete meta.properties.uuid
          delete meta.properties.shortname
          delete meta.properties.created_at
          delete meta.properties.updated_at
          selectedSchemaContent = meta
          entryContent.json = generateObjectFromSchema(meta)
          entryContent.json.is_active = true
      }
      else if (new_resource_type === ResourceType.permission) {
          const meta = metaPermissionSchema;
          delete meta.properties.uuid
          delete meta.properties.shortname
          delete meta.properties.created_at
          delete meta.properties.updated_at
          selectedSchemaContent = meta
          entryContent.json = generateObjectFromSchema(meta)
          entryContent.json.is_active = true
      }
      else if (new_resource_type === ResourceType.role) {
          const meta = metaRoleSchema;
          delete meta.properties.uuid
          delete meta.properties.shortname
          delete meta.properties.created_at
          delete meta.properties.updated_at
          selectedSchemaContent = meta
          entryContent.json = generateObjectFromSchema(meta)
          entryContent.json.is_active = true
      } else {
          let meta: any = structuredClone($metadata);
          if (selectedSchema==="workflow"){
              meta.properties = {
                  ...meta.properties,
                  "is_open": {
                      "type": "boolean"
                  },
                  "workflow_shortname": {
                      "type": "string"
                  },
                  "state": {
                      "type": "string"
                  },
                  "reporter": {
                      "type": "string"
                  },
                  "resolution_reason": {
                      "type": "string"
                  },
                  "receiver": {
                      "type": "string"
                  }
              }
          }
          selectedSchemaContent = meta ?? {};
          baseEntryContent = generateObjectFromSchema(meta ?? {});
          entryContent.json = baseEntryContent;
          entryContent.json.is_active = true
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
  $: {
    if (oldSelectedSchema !== selectedSchema && selectedSchema !== '') {
      (async () => {
        let _selectedSchemaContent;
        if (["folder_rendering"].includes(selectedSchema)){
            _selectedSchemaContent = await retrieve_entry(
                ResourceType.schema,
                "management",
                "schema",
                selectedSchema,
                true
            );
        } else {
            _selectedSchemaContent = await retrieve_entry(
                ResourceType.schema,
                space_name,
                "schema",
                selectedSchema,
                true
            );
        }

        selectedSchemaContent.properties.payload = _selectedSchemaContent?.payload?.body ?? {};
        cleanUpSchema(selectedSchemaContent.properties);
        validatorContent = createAjvValidator({ schema:  selectedSchemaContent });
        const body = generateObjectFromSchema(structuredClone(selectedSchemaContent));
        entryContent.json.payload.body = body ?? {};
      })();
      oldSelectedSchema = selectedSchema;
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
    let result;
    const _schemas = schemas.records.map((e) => e.shortname);
    if (entryType === "folder"){
        result = ["folder_rendering", ..._schemas];
    } else {
        result = _schemas.filter((e) => !["meta_schema", "folder_rendering"].includes(e));
    }
    if (entry?.payload?.body?.content_schema_shortnames){
        result = result.filter((e) => entry?.payload?.body?.content_schema_shortnames.includes(e));
    }
    return result;
  }

  const isContentPreviewable: boolean = resource_type === ResourceType.content
      && !!entry?.payload?.content_type
      && !!entry?.payload?.body;

  $: {
      if (!isDeepEqual(entryContent, selectedSchemaData)) {
          const _entryContent = entryContent.json
              ? structuredClone(entryContent.json)
              : JSON.parse(entryContent.text);
          const _selectedSchemaData = selectedSchemaData.json
              ? structuredClone(selectedSchemaData.json)
              : JSON.parse(selectedSchemaData.text);

          if (Object.keys(_selectedSchemaData?.json ?? {}).length){
            if (!isContentEntryInForm) {
                entryContent = {
                    json: {
                      ..._entryContent,
                      ..._selectedSchemaData,
                    },
                    text: undefined
                };
            }
            else {
                // selectedSchemaData.json = {
                //     ..._selectedSchemaData,
                //     ..._entryContent,
                // };
                // selectedSchemaData.text = undefined;
            }
          }
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
    Creating a {new_resource_type} under
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
                  {#each [
                      ContentType.json,
                      ContentType.text,
                      ContentType.markdown,
                      ContentType.html,
                  ] as type}
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
                <SchemaEditor bind:content={schemaContent} />
              </TabPane>
              <TabPane tabId="editor" tab="Editor">
                <JSONEditor
                  bind:content={schemaContent}
                  onRenderMenu={handleRenderMenu}
                  mode={Mode.text}
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
                <Label class="mt-3">{
                    new_resource_type === ResourceType.permission
                        ? "Permission definition"
                        : new_resource_type === ResourceType.role
                            ? "Role definition"
                            : "Payload"
                }</Label>
                <TabContent on:tab={(e) => (isContentEntryInForm = e.detail==="form")}>
                  {#if selectedSchemaContent && Object.keys(selectedSchemaContent).length !== 0}
                  <TabPane tabId="form" tab="Form" active>
                    <SchemaForm
                      bind:ref={schemaFormRefModal}
                      schema={selectedSchemaContent}
                      bind:data={selectedSchemaData.json}
                    />
                  </TabPane>
                 {/if}
                  <TabPane tabId="editor" tab="Editor" active={selectedSchemaContent && Object.keys(selectedSchemaContent).length === 0}>
                    <JSONEditor
                      bind:content={entryContent}
                      bind:validator={validatorContent}
                      onRenderMenu={handleRenderMenu}
                      mode={Mode.text}
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

{#if entry}
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
        {#if [ResourceType.folder, ResourceType.space].includes(resource_type)}
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

          {#if resource_type === ResourceType.schema && !["meta_schema"].includes(entry.shortname)}
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
        {#if !!entry?.payload?.body?.allow_csv}
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
        {/if}
      </ButtonGroup>
      {#if [ResourceType.space, ResourceType.folder].includes(resource_type)}
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
          {#if !!entry?.payload?.body?.stream}
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
          {/if}
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
      <ListView {space_name} {subpath}
                folderColumns={entry?.payload?.body?.index_attributes ?? null}
                sort_by={entry?.payload?.body?.sort_by ?? null}
                sort_order={entry?.payload?.body?.sort_order ?? null}
      />
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
          {#if isContentPreviewable}
            <TabPane tabId="content" tab="Content" class="p-3" active>
              {#if entry.payload.content_type === ContentType.html}
                {@html entry.payload.body}
              {:else if entry.payload.content_type === ContentType.text}
                <textarea value={entry.payload.body.toString()} disabled/>
              {:else if entry.payload.content_type === ContentType.markdown}
                {@html marked(entry.payload.body.toString())}
              {:else if entry.payload.content_type === ContentType.json}
                <Prism code={entry.payload.body} />
              {/if}
            </TabPane>
          {/if}
          <TabPane tabId="table" tab="Table" active={!isContentPreviewable}><Table2Cols entry={{"Resource type": resource_type,...entry}} /></TabPane>
          <TabPane tabId="form" tab="Raw"><Prism code={entry} /></TabPane>
        </TabContent>
      </div>
    </div>
    <div class="tab-pane" class:active={tab_option === "edit_meta"}>
      {#if tab_option === "edit_meta"}
        <div
                class="px-1 pb-1 h-100"
                style="text-align: left; direction: ltr; overflow: hidden auto;"
        >
          <JSONEditor
                  bind:content={contentMeta}
                  bind:validator={validatorMeta}
                  onRenderMenu={handleRenderMenu}
                  mode={Mode.text}
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
                    bind:content={contentContent}
                    bind:validator
                    onRenderMenu={handleRenderMenu}
                    mode={Mode.text}
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
          {#if resource_type === ResourceType.schema}
            <SchemaEditor bind:content={contentContent} />
          {:else if resource_type === ResourceType.content && schema_name === "configuration"}
            <ConfigEditor entries={contentContent.json.items} />
          {:else if resource_type === ResourceType.content && schema_name === "translation"}
            <TranslationEditor bind:entries={contentContent.json.items} columns={Object.keys(schema.properties.items.items.properties)} />
          {:else}
            <div class="px-1 pb-1 h-100">
              <SchemaForm
                      bind:ref={schemaFormRefContent}
                      {schema}
                      bind:data={contentContent.json}
              />
            </div>
          {/if}
        </div>
      {/if}
    {/if}
    {#if resource_type === ResourceType.schema && !["meta_schema"].includes(entry.shortname)}
      <div class="tab-pane" class:active={tab_option === "visualization"}>
        <div
                class="px-1 pb-1 h-100"
                style="text-align: left; direction: ltr; overflow: hidden auto;"
        >
          <div class="preview">
            {JSON.stringify(["meta_schema"].includes(entry.shortname))}
            {#if ["meta_schema"].includes(entry.shortname)}
              <a
                      href={"https://www.plantuml.com/plantuml/svg/" +
              schemaVisualizationEncoder(entry.payload.body)}
                      download="{entry.shortname}.svg"
              >
                <img
                        src={"https://www.plantuml.com/plantuml/svg/" +
                schemaVisualizationEncoder(entry.payload.body)}
                        alt={entry.shortname}
                />
              </a>
            {:else}
              <a
                      href={"https://www.plantuml.com/plantuml/svg/" +
              schemaVisualizationEncoder(entry.payload.body.properties)}
                      download="{entry.shortname}.svg"
              >
                <img
                        src={"https://www.plantuml.com/plantuml/svg/" +
                schemaVisualizationEncoder(entry.payload.body.properties)}
                        alt={entry.shortname}
                />
              </a>
            {/if}
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
              {resource_type}
              {space_name}
              {subpath}
              parent_shortname={entry.shortname}
              attachments={Object.values(entry.attachments)}
      />
    </div>
  </div>
{:else}
  <Alert color="danger text-center mt-5">
    <h4 class="alert-heading text-capitalize">Failed to load the entry, please check its existence or try again.</h4>
  </Alert>
{/if}

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
