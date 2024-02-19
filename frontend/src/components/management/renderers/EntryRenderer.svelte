<script lang="ts">
  import { onDestroy, onMount } from "svelte";
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
    TabPane,
  } from "sveltestrap";
  import Icon from "../../Icon.svelte";
  import { _ } from "@/i18n";
  import ListView from "../ListView.svelte";
  import Prism from "@/components/Prism.svelte";
  import {
    createAjvValidator,
    JSONEditor,
    Mode,
    Validator,
  } from "svelte-jsoneditor";
  import { status_line } from "@/stores/management/status_line";
  import { authToken } from "@/stores/management/auth";
  import { timeAgo } from "@/utils/timeago";
  import { Level, showToast } from "@/utils/toast";
  import { faSave } from "@fortawesome/free-regular-svg-icons";
  import refresh_spaces from "@/stores/management/refresh_spaces";
  import { website } from "@/config";
  import HtmlEditor from "../editors/HtmlEditor.svelte";
  import MarkdownEditor from "../editors/MarkdownEditor.svelte";
  import SchemaEditor from "@/components/management/editors/SchemaEditor.svelte";
  import checkAccess, { checkAccessv2 } from "@/utils/checkAccess";
  import { fade } from "svelte/transition";
  import BreadCrumbLite from "../BreadCrumbLite.svelte";
  import downloadFile from "@/utils/downloadFile";
  import SchemaForm from "svelte-jsonschema-form";
  import Table2Cols from "@/components/management/Table2Cols.svelte";
  import Attachments from "@/components/management/Attachments.svelte";
  import HistoryListView from "@/components/management/HistoryListView.svelte";
  import { marked } from "marked";
  import {
    generateObjectFromSchema,
    managementEntities,
    resolveResourceType,
  } from "@/utils/renderer/rendererUtils";
  import TranslationEditor from "@/components/management/editors/TranslationEditor.svelte";
  import ConfigEditor from "@/components/management/editors/ConfigEditor.svelte";
  import { metadata } from "@/stores/management/metadata";
  import metaUserSchema from "@/validations/meta.user.json";
  import metaRoleSchema from "@/validations/meta.role.json";
  import metaPermissionSchema from "@/validations/meta.permission.json";
  import PlantUML from "@/components/management/PlantUML.svelte";
  import ContentEditor from "@/components/management/ContentEditor.svelte";
  import TicketEntryRenderer from "@/components/management/renderers/TicketEntryRenderer.svelte";
  import WorkflowRenderer from "@/components/management/renderers/WorkflowRenderer.svelte";
  import UserEntryRenderer from "@/components/management/renderers/UserEntryRenderer.svelte";
  import PermissionForm from "./Forms/PermissionForm.svelte";
  import RoleForm from "./Forms/RoleForm.svelte";
  import UserForm from "@/components/management/renderers/Forms/UserForm.svelte";
  import {bulkBucket} from "@/stores/management/bulk_bucket";

  // props
  export let entry: ResponseEntry;
  export let space_name: string;
  export let subpath: string;
  export let resource_type: ResourceType;
  export let schema_name: string | undefined = null;
  export let refresh = {};

  // auth
  const canCreateFolder = checkAccessv2(
    "create",
    space_name,
    subpath,
    ResourceType.folder
  );
  let canCreateEntry = false;
  const canUpdate = checkAccessv2("update", space_name, subpath, resource_type);
  const canDelete =
    checkAccessv2("delete", space_name, subpath, resource_type) &&
    !(space_name === "management" && subpath === "/");

  // misc
  let header_height: number;
  let ws = null;
  let schema = null;
  let isNeedRefresh = false;

  // view
  let tab_option =
    resource_type === ResourceType.folder ||
    resource_type === ResourceType.space
      ? "list"
      : "view";
  const isContentPreviewable: boolean =
    resource_type === ResourceType.content &&
    !!entry?.payload?.content_type &&
    !!entry?.payload?.body;

  // editors
  //// meta
  let jseMeta: any = { text: "{}" };
  let validatorMeta: Validator = setMetaValidator();
  let oldJSEMeta = structuredClone(jseMeta);
  /// content (payload)
  let jseContent: any = { text: "{}" };
  let validatorModalContent: Validator = createAjvValidator({ schema: {} });
  let validatorContent: Validator = createAjvValidator({ schema: {} });
  let oldJSEContent = { json: {}, text: undefined };
  /// schema
  // let selectedSchemaContent: any = {};
  // let selectedSchemaData: any = {json:{}, text: undefined};
  /// handler
  let errorContent = null;
  /// ref
  let jseMetaRef;
  let schemaContentRef;
  let jseContentRef;
  // let schemaFormRefModal;
  let schemaFormRefContent;

  // modal
  /// flags
  let isModalOpen = false;
  let entryType = "folder";
  let isSchemaEntryInForm = true;
  let isModalContentEntryInForm = true;
  /// content
  let schemaContent = { json: {}, text: undefined };
  let contentShortname = "";
  let workflowShortname = "";
  let selectedSchema = subpath === "workflows" ? "workflow" : null;
  let selectedContentType = ContentType.json;
  let new_resource_type: ResourceType;

  let payloadFiles: FileList;
  // editors
  let jseModalMetaRef;
  let jseModalMeta: any = { text: "{}" };
  let jseModalContentRef;
  let jseModalContent: any = { text: "{}" };
  let formModalContent: any;
  let formModalContentPayload: any = { json: {}, text: undefined };

  let allowedResourceTypes = [ResourceType.content];
  function setMetaValidator(): Validator {
    let schema = {};
    switch (resource_type) {
      case ResourceType.user:
        schema = metaUserSchema;
        break;
      case ResourceType.permission:
        schema = metaPermissionSchema;
        break;
      case ResourceType.role:
        schema = metaRoleSchema;
        break;
      default:
        schema = structuredClone($metadata);
        break;
    }
    return createAjvValidator({
      schema: schema,
    });
  }
  onMount(async () => {
    if (entry) {
      const cpy = structuredClone(entry);
      if (entry?.payload) {
        if (entry?.payload?.content_type === "json") {
          jseContentRef.set({
            text: JSON.stringify(cpy?.payload?.body ?? {}, null, 2),
          });
        } else {
          jseContent = cpy?.payload?.body;
        }
      }
      delete cpy?.payload?.body;
      delete cpy?.attachments;

      // jseMeta.text = JSON.stringify(cpy,null,2)
      if (jseMetaRef) {
        jseMetaRef.set({ text: JSON.stringify(cpy, null, 2) });
        oldJSEMeta = structuredClone(jseMeta);
      }

      try {
          await checkWorkflowsSubpath();
      } catch (e) {

      }

      try {
          if (entry?.payload?.schema_shortname) {
              const entrySchema = entry?.payload?.schema_shortname;
              let _schema: any = null;

              _schema = await retrieve_entry(
                  ResourceType.schema,
                  ["folder_rendering"].includes(entrySchema)
                      ? "management"
                      : space_name,
                  "schema",
                  entrySchema,
                  true
              );

              if (_schema) {
                  schema = _schema.payload?.body;
                  validatorContent = createAjvValidator({ schema });
              } else {
                  showToast(
                      Level.warn,
                      `Can't load the schema ${entry?.payload?.schema_shortname} !`
                  );
              }
          }
      } catch (e){

      }

      allowedResourceTypes.push(
          resolveResourceType(
            space_name,
            subpath,
            null
        )
      )

      console.log({allowedResourceTypes})
      allowedResourceTypes.map(r=> {
          console.log("create", space_name, subpath, r);
      })

      canCreateEntry = allowedResourceTypes.map(r=>checkAccessv2("create", space_name, subpath, r)).some(item => item);

      status_line.set(
        `<small>Last updated: <strong>${timeAgo(
          new Date(entry.updated_at)
        )}</strong><br/>Attachments: <strong>${
          Object.keys(entry.attachments).length
        }</strong></small>`
      );

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
    }
  });

  onDestroy(() => {
    status_line.set("");

    if (isWSOpen(ws)) {
      ws.send(JSON.stringify({ type: "notification_unsubscribe" }));
    }
    if (ws != null) ws.close();
  });

  function isWSOpen(ws: any) {
    return ws != null && ws.readyState === ws.OPEN;
  }

  async function checkWorkflowsSubpath() {
    try {
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
      allowedResourceTypes.push(ResourceType.ticket);
    }
    if ((entry?.payload?.body?.content_resource_types ?? []).length) {
      const content_resource_types =
        entry?.payload?.body?.content_resource_types;
      allowedResourceTypes = allowedResourceTypes.filter((e) =>
        content_resource_types.includes(e)
      );
    }
    } catch (error) {}
  }

  async function handleSave(e: Event) {
    e.preventDefault();
    // if (!isSchemaValidated) {
    //   alert("The content does is not validated agains the schema");
    //   return;
    // }
    errorContent = null;

    const x = jseMeta.json
      ? structuredClone(jseMeta.json)
      : JSON.parse(jseMeta.text);

    let data: any = structuredClone(x);
    if (entry?.payload) {
      if (entry?.payload?.content_type === "json") {
        if (tab_option === "edit_content_form") {
          if (schemaFormRefContent && !schemaFormRefContent.reportValidity()) {
            return;
          }
        }
        const y = jseContent.json
          ? structuredClone(jseContent.json)
          : JSON.parse(jseContent.text);

        if (new_resource_type === "schema") {
          if (isSchemaEntryInForm) {
            delete y.name;
          }
        }

        if (data.payload) {
          data.payload.body = y;
        }
      } else {
        data.payload.body = jseContent;
      }
    }

    if (resource_type === ResourceType.user && btoa(data.password.slice(0,6)) === 'JDJiJDEy') {
      delete data.password;
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
    if (resource_type === ResourceType.space) {
      request_data.request_type = RequestType.update;
      request_data.records[0].resource_type = ResourceType.space;
      response = await space(request_data);
    } else {
      response = await request(request_data);
    }

    if (response.status == Status.success) {
      showToast(Level.info);
      oldJSEMeta = structuredClone(jseMeta);

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
    } else {
      errorContent = response;
      showToast(Level.warn);
    }
  }

  function handleRenderMenu(
    items: any,
    context: { mode: "tree" | "text" | "table"; modal: boolean }
  ) {
    items = items.filter(
      (item) => !["tree", "text", "table"].includes(item.text)
    );
    const separator = {
      separator: true,
    };

    const itemsWithoutSpace = items.slice(0, items.length - 2);
    if (isModalOpen) {
      return itemsWithoutSpace.concat([
        separator,
        {
          space: true,
        },
      ]);
    } else {
      return itemsWithoutSpace.concat([
        separator,
        {
          onClick: handleSave,
          icon: faSave,
          title: "Save",
        },
        {
          space: true,
        },
      ]);
    }
  }

  async function handleSubmit(event: Event) {
    event.preventDefault();

    let response: any;
    let request_body: any = {};
    if (new_resource_type === "schema") {
      let body = schemaContent.json
        ? structuredClone(schemaContent.json)
        : JSON.parse(schemaContent.text);

      if (isSchemaEntryInForm) {
        delete body.name;
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
                body: body,
              },
            },
          },
        ],
      };
      response = await request(request_body);
    }
    else if (new_resource_type === ResourceType.user) {

      // if (!schemaFormRefModal.reportValidity()) {
      //     return;
      // }

      let body: any;
      // if (isModalContentEntryInForm){
      //     body = selectedSchemaData.json
      //         ? structuredClone(selectedSchemaData.json)
      //         : JSON.parse(selectedSchemaData.text);
      //     body = {
      //         attributes: body
      //     }
      // } else {

        if (isModalContentEntryInForm){
            body = {}
            formModalContent.forEach(item => {
                body[item.key] = item.value;
            });
            body = structuredClone(body);
            if (typeof body.roles === 'string'){
                body.roles = body.roles.split(",");
            }

            const formModalContentPayloadJson = formModalContentPayload.json
                ? structuredClone(formModalContentPayload.json)
                : JSON.parse(formModalContentPayload.text);

            if (Object.keys(formModalContentPayloadJson).length){
                jseModalContent = {
                    json: formModalContentPayloadJson
                };
                body.payload = {
                    content_type: "json",
                    schema_shortname: selectedSchema,
                    body: formModalContentPayloadJson
                }
            }
        }
        else {
            body = jseModalContent.json
                ? structuredClone(jseModalContent.json)
                : JSON.parse(jseModalContent.text);
        }
      // }

      if (!body?.password) {
        showToast(Level.warn, "Password must be provided!");
        return;
      }
      else {
        if (!passwordRegExp.test(body?.password)) {
          showToast(Level.warn, passwordWrongExp);
          return;
        }
      }

      const shortnameStatus: any = await check_existing(
        "shortname",
        contentShortname
      );
      if (!shortnameStatus.attributes.unique) {
        showToast(Level.warn, "Shortname already exists!");
        return;
      }

      if (body.email) {
        const emailStatus: any = await check_existing("email", body.email);
        if (!emailStatus.attributes.unique) {
          showToast(Level.warn, "Email already exists!");
          return;
        }
      }
      else {
        delete body.email;
      }

      if (body.msisdn) {
        const msisdnStatus: any = await check_existing("msisdn", body.msisdn);
        if (msisdnStatus) {
            if (!msisdnStatus.attributes.unique) {
                showToast(Level.warn, "MSISDN already exists!");
                return;
            }
        } else {
            showToast(Level.warn, "Please double check your MSISDN!");
            return;
        }

      }
      else {
        delete body.msisdn;
      }

      if (body.is_active === undefined) {
        body.is_active = true;
      }
      if (body.invitation === undefined) {
        body.invitation = "sysadmin";
      }
      if (!!body.type === false) {
        body.type = "web";
      }
      if (!!body.language === false) {
        delete body.language;
      }

      const request_body = {
        shortname: contentShortname,
        resource_type: ResourceType.user,
        subpath: "users",
        attributes: body,
      };
      response = await request({
          request_type: RequestType.create,
          space_name: "management",
          records: [request_body]
      });
    } else if (entryType === "content") {
      if (selectedContentType === "json") {
        let body: any;

        if (jseModalContentRef?.validate()?.validationErrors) {
          return;
        }
        // if (isModalContentEntryInForm){
        //     if (
        //         selectedSchemaContent != null &&
        //         selectedSchemaData.json
        //     ) {
        //         // if (!schemaFormRefModal.reportValidity()) {
        //         //     return;
        //         // }
        //         body = selectedSchemaData.json;
        //     }
        // }
        // else {
        body = jseModalContent.json
          ? structuredClone(jseModalContent.json)
          : JSON.parse(jseModalContent.text);
        // }

        if (isModalContentEntryInForm) {
          if (new_resource_type === ResourceType.role) {
            body.permissions = formModalContent;
          }
          if (new_resource_type === ResourceType.permission) {
            body = {
              ...body,
              ...formModalContent,
            };
          }
        }

        if (
          new_resource_type === ResourceType.role ||
          new_resource_type === ResourceType.permission
        ) {
          request_body = {
            space_name,
            request_type: RequestType.create,
            records: [
              {
                resource_type: new_resource_type,
                shortname: contentShortname === "" ? "auto" : contentShortname,
                subpath,
                attributes: {
                  is_active: true,
                  ...body,
                },
              },
            ],
          };
        } else {
          if (workflowShortname) {
            request_body = {
              ...request_body,
              workflow_shortname: workflowShortname,
            };
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
                  is_active: true,
                  ...request_body,
                },
              },
            ],
          };
        }
        if (new_resource_type === ResourceType.ticket) {
          request_body.records[0].attributes.workflow_shortname =
            workflowShortname;
          selectedContentType = ContentType.json;
        }
        if (
          selectedContentType !== null &&
          new_resource_type !== ResourceType.role &&
          new_resource_type !== ResourceType.permission
        ) {
          request_body.records[0].attributes.payload = {
            content_type: "json",
            schema_shortname: selectedSchema,
            body: body,
          };
        }
        response = await request(request_body);
      } else if (["text", "html", "markdown"].includes(selectedContentType)) {
        request_body = {
          space_name,
          request_type: RequestType.create,
          records: [
            {
              resource_type: new_resource_type,
              shortname: contentShortname === "" ? "auto" : contentShortname,
              subpath,
              attributes: {
                is_active: true,
                payload: {
                  content_type: selectedContentType,
                  body: jseModalContent,
                },
              },
            },
          ],
        };
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
          null,
          contentShortname === "" ? "auto" : contentShortname,
          payloadFiles[0]
        );
      }
    } else if (entryType === "folder") {
      let body: any = {};
      // if (isModalContentEntryInForm){
      //     body = selectedSchemaData.json
      //         ? structuredClone(selectedSchemaData.json)
      //         : JSON.parse(selectedSchemaData.text);
      // } else {
      body = jseModalContent.json
        ? structuredClone(jseModalContent.json)
        : JSON.parse(jseModalContent.text);
      // }
      if (!!body.query.type === false) {
        body.query.type = "search";
      }
      if (!!body.sort_type === false) {
        body.sort_type = "ascending";
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
              is_active: true,
              payload: {
                content_type: "json",
                schema_shortname: "folder_rendering",
                body: body ?? {},
              },
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
    } else {
      showToast(Level.warn);
      errorContent = response.error;
    }
  }

  async function handleDelete() {
    if (
      confirm(`Are you sure want to delete ${entry.shortname} entry ?`) ===
      false
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
    if (resource_type !== ResourceType.space) {
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
    }
    else {
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
  async function handleDeleteBulk() {
    if (
      confirm(`Are you sure want to delete (${$bulkBucket.map(e=>e.shortname).join(", ")}) ${$bulkBucket.length === 1 ? "entry" : "entries"} ?`) ===
      false
    ) {
      return;
    }

      const records = []
      $bulkBucket.map(b => {
          records.push({
              resource_type: b.resource_type,
              shortname: b.shortname,
              subpath: subpath || "/",
              branch_name: "master",
              attributes: {},
          });
      });

    const request_body = {
      space_name,
      request_type: RequestType.delete,
      records: records,
    };
    const response = await request(request_body);

    if (response?.status === "success") {
      showToast(Level.info);
      window.location.reload();
    } else {
      showToast(Level.warn);
    }
  }

  // function beforeUnload(event) {
  //     if (!isDeepEqual(removeEmpty(jseMeta), removeEmpty(oldJSEMeta))) {
  //         event.preventDefault();
  //         if (
  //             confirm("You have unsaved changes, do you want to leave ?") === false
  //         ) {
  //             return false;
  //         }
  //     }
  // }

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

  const modalToggle = () => {
    isModalOpen = !isModalOpen;
    contentShortname = "";
  };

  function setPrepModalContentPayloadFromLocalSchema() {
    let meta: any = {};
    if (new_resource_type === ResourceType.user) {
      meta = structuredClone(metaUserSchema);
      delete meta.properties.uuid;
      delete meta.properties.shortname;
      delete meta.properties.created_at;
      delete meta.properties.updated_at;
      delete meta.properties.payload;
      // selectedSchemaContent = meta
      jseModalContent = {
        text: JSON.stringify(generateObjectFromSchema(meta), null, 2),
      };
      // jseContentRef.set({text: generateObjectFromSchema(meta)})
      validatorModalContent = createAjvValidator({ schema: meta });
    }
    else if (new_resource_type === ResourceType.permission) {
      meta = structuredClone(metaPermissionSchema);
      delete meta.properties.uuid;
      delete meta.properties.shortname;
      delete meta.properties.created_at;
      delete meta.properties.updated_at;
      // selectedSchemaContent = meta
      // jseContent.json = generateObjectFromSchema(meta)
      jseModalContent = {
        text: JSON.stringify(generateObjectFromSchema(meta), null, 2),
      };
      validatorModalContent = createAjvValidator({ schema: meta });
    }
    else if (new_resource_type === ResourceType.role) {
      meta = structuredClone(metaRoleSchema);
      delete meta.properties.uuid;
      delete meta.properties.shortname;
      delete meta.properties.created_at;
      delete meta.properties.updated_at;
      delete meta.properties.updated_at;
      // jseContent.json = generateObjectFromSchema(meta)
      jseModalContent = {
        text: JSON.stringify(generateObjectFromSchema(meta), null, 2),
      };
      validatorModalContent = createAjvValidator({ schema: meta });
    }
  }
  async function setPrepModalContentPayloadFromFetchedSchema() {
    let schemaContent;
    if (["folder_rendering"].includes(selectedSchema)) {
      schemaContent = await retrieve_entry(
        ResourceType.schema,
        "management",
        "schema",
        selectedSchema,
        true
      );
    }
    else {
      schemaContent = await retrieve_entry(
        ResourceType.schema,
        space_name,
        "schema",
        selectedSchema,
        true,
        false
      );
    }
    if (schemaContent === null) {
      showToast(Level.warn, `Can't load the schema ${selectedSchema} !`);
      return;
    }
    let _schema = schemaContent.payload.body;
    if (new_resource_type === ResourceType.user) {
      const _metaUserSchema = structuredClone(metaUserSchema);
      delete _metaUserSchema.properties.uuid;
      delete _metaUserSchema.properties.shortname;
      delete _metaUserSchema.properties.created_at;
      delete _metaUserSchema.properties.updated_at;
      delete _metaUserSchema.properties.payload.properties.last_validated;
      delete _metaUserSchema.properties.payload.properties.validation_status;
      _metaUserSchema.properties.payload.properties.body = _schema;
      _schema = _metaUserSchema;

      validatorModalContent = createAjvValidator({ schema: _schema });
      const body: any = generateObjectFromSchema(structuredClone(_schema));
      formModalContentPayload = {
          text: JSON.stringify(
              generateObjectFromSchema(structuredClone(_metaUserSchema.properties.payload.properties.body)),
              null,
              2
          )
      };

      body.payload.content_type = "json";
      body.payload.schema_shortname = selectedSchema;
      jseModalContent = { text: JSON.stringify(body, null, 2) };
    } else {
      validatorModalContent = createAjvValidator({ schema: _schema });
      const body: any = generateObjectFromSchema(structuredClone(_schema));
      jseModalContent = { text: JSON.stringify(body, null, 2) };
    }
    oldSelectedSchema = selectedSchema;
  }

  function setSchemaItems(schemas): Array<string> {
    if (schemas === null) {
      return [];
    }
    let result;
    const _schemas = schemas.records.map((e) => e.shortname);
    if (entryType === "folder") {
      result = ["folder_rendering", ..._schemas];
    } else {
      result = _schemas.filter(
        (e) => !["meta_schema", "folder_rendering"].includes(e)
      );
    }
    if ((entry?.payload?.body?.content_schema_shortnames ?? []).length) {
      result = result.filter((e) =>
        entry?.payload?.body?.content_schema_shortnames.includes(e)
      );
    }
    return result;
  }
  function setWorkflowItem(workflows): Array<string> {
    if (workflows === null) {
      return [];
    }
    return workflows.records.map((e) => e.shortname);
  }

  $: {
    if (selectedContentType === "json") {
      jseModalContent = { text: "{}" };
    } else {
      jseModalContent = "";
    }
  }

  let old_new_resource_type = undefined;
  $: {
    if (old_new_resource_type !== new_resource_type
    && [ResourceType.user, ResourceType.permission, ResourceType.role].includes(new_resource_type)) {
      setPrepModalContentPayloadFromLocalSchema();
    }
  }

  let oldSelectedSchema = null;
  $: {
    if (selectedSchema === null){
        validatorModalContent = createAjvValidator({ schema: {} });
        jseModalContent = { text: JSON.stringify({}, null, 2) };
        oldSelectedSchema = null;
    }
    else if (selectedSchema !== oldSelectedSchema) {
      setPrepModalContentPayloadFromFetchedSchema();
    }
  }

  function handleCreateEntryModal() {
    entryType = "content";
    isModalOpen = true;
    new_resource_type = resolveResourceType(
      space_name,
      subpath,
      allowedResourceTypes.length
        ? allowedResourceTypes[0]
        : ResourceType.content
    );
    selectedSchema = null;
    if (
      [ResourceType.user, ResourceType.permission, ResourceType.role].includes(
        new_resource_type
      )
    ) {
      setPrepModalContentPayloadFromLocalSchema();
    } else if (selectedSchema) {
      setPrepModalContentPayloadFromFetchedSchema();
    }
  }
</script>

<!--<svelte:window on:beforeunload={beforeUnload} />-->

<Modal
  isOpen={isModalOpen}
  toggle={modalToggle}
  size={new_resource_type === "schema" ? "xl" : "lg"}
>
  <ModalHeader toggle={modalToggle}>
    Creating a {new_resource_type} under
    <span class="text-success">{space_name}</span>/<span class="text-primary"
      >{subpath}</span
    >
  </ModalHeader>
  <Form on:submit={async (e) => await handleSubmit(e)}>
    <ModalBody>
      <FormGroup>
        {#if entryType !== "folder"}
          {#if !managementEntities.some( (m) => `${space_name}/${subpath}`.endsWith(m) )}
            <Label for="resource_type" class="mt-3">Resource type</Label>
            <Input
              id="resource_type"
              bind:value={new_resource_type}
              type="select"
            >
              {#each allowedResourceTypes as type}
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
                {#each [ContentType.json, ContentType.text, ContentType.markdown, ContentType.html] as type}
                  <option value={type}>{type}</option>
                {/each}
              </Input>
            {/if}
            {#if new_resource_type === "ticket"}
              {#await query( { space_name, type: QueryType.search, subpath: "/workflows", search: "", retrieve_json_payload: true, limit: 99 } ) then workflows}
                <Label class="mt-3">Workflow</Label>
                {#if setWorkflowItem(workflows).length === 0}
                  <Input bind:value={workflowShortname} />
                {:else}
                  <Input bind:value={workflowShortname} type="select">
                    {#each setWorkflowItem(workflows) as workflow}
                      <option value={workflow}>{workflow}</option>
                    {/each}
                  </Input>
                {/if}
              {/await}
            {/if}
          {/if}
        {/if}

        {#if !["workflows", "schema"].includes(subpath) && ![ResourceType.folder, ResourceType.role, ResourceType.permission].includes(new_resource_type)}
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
        {#if new_resource_type === "schema"}
          <TabContent
            on:tab={(e) => (isSchemaEntryInForm = e.detail === "form")}
          >
            <TabPane tabId="form" tab="Forms" active>
              <SchemaEditor bind:content={schemaContent} />
            </TabPane>
            <TabPane tabId="editor" tab="Editor">
              <JSONEditor
                bind:this={schemaContentRef}
                bind:content={schemaContent}
                onRenderMenu={handleRenderMenu}
                mode={Mode.text}
              />
            </TabPane>
          </TabContent>
          <Row></Row>
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
            <Label class="mt-3">
              {new_resource_type === ResourceType.permission
                ? "Permission definition"
                : new_resource_type === ResourceType.role
                  ? "Role definition"
                  : "Payload"}
            </Label>
            <!--              <TabContent on:tab={(e) => (isModalContentEntryInForm = e.detail==="form")}>-->
            <!--{#if selectedSchemaContent && Object.keys(selectedSchemaContent).length !== 0}-->
            <!--  <TabPane tabId="form" tab="Form" active>-->
            <!--    <SchemaForm-->
            <!--      bind:ref={schemaFormRefModal}-->
            <!--      schema={selectedSchemaContent}-->
            <!--      bind:data={selectedSchemaData.json}-->
            <!--    />-->
            <!--  </TabPane>-->
            <!--{/if}-->
            <!--                <TabPane tabId="editor" tab="Editor" active={selectedSchemaContent && Object.keys(selectedSchemaContent).length === 0}>-->

            {#if [ResourceType.user, ResourceType.permission, ResourceType.role].includes(new_resource_type)}
            <TabContent
              on:tab={(e) => (isModalContentEntryInForm = e.detail === "form")}
            >
              <TabPane tabId="form" tab="Form" active>
                {#if new_resource_type === ResourceType.permission}
                  <PermissionForm bind:content={formModalContent} />
                {:else if new_resource_type === ResourceType.role}
                  <RoleForm bind:content={formModalContent} />
                {:else if new_resource_type === ResourceType.user}
                  <UserForm bind:content={formModalContent} bind:payload={formModalContentPayload}/>
                {/if}
              </TabPane>
              <TabPane tabId="editor" tab="Editor">
                <JSONEditor
                  bind:this={jseModalContentRef}
                  bind:content={jseModalContent}
                  bind:validator={validatorModalContent}
                  onRenderMenu={handleRenderMenu}
                  mode={Mode.text}
                />
              </TabPane>
            </TabContent>
            {:else}
              <JSONEditor
                bind:this={jseModalContentRef}
                bind:content={jseModalContent}
                bind:validator={validatorModalContent}
                onRenderMenu={handleRenderMenu}
                mode={Mode.text}
              />
            {/if}
          {/if}
          {#if selectedContentType === "text"}
            <Label class="mt-3">Payload</Label>
            <Input type="textarea" bind:value={jseModalContent} />
          {/if}
          {#if selectedContentType === "html"}
            <Label class="mt-3">Payload</Label>
            <HtmlEditor bind:content={jseModalContent} />
          {/if}
          {#if selectedContentType === "markdown"}
            <Label class="mt-3">Payload</Label>
            <MarkdownEditor bind:content={jseModalContent} />
          {/if}
        {/if}
        <hr />
        {#if errorContent}
          <h3 class="mt-3">Error:</h3>
          <Prism bind:code={errorContent} />
        {/if}
        <hr />
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
            {#if selectedSchema === "workflow"}
              <Button
                outline
                color="success"
                size="sm"
                class="justify-content-center text-center py-0 px-1"
                active={"workflow" === tab_option}
                title={$_("edit") + " payload"}
                on:click={() => (tab_option = "workflow")}
              >
                <Icon name="diagram-3" />
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
        {#if canCreateEntry || canCreateFolder || canDelete || !!entry?.payload?.body?.allow_csv}
          <span class="ps-2 pe-1"> {$_("actions")} </span>
        {/if}
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
          {#if $bulkBucket.length}
          <Button
            outline
            color="success"
            size="sm"
            title={$_("delete_selected")}
            on:click={handleDeleteBulk}
            class="justify-content-center text-center py-0 px-1"
          >
            <Icon name="x-circle" />
          </Button>
          {/if}
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

      <ButtonGroup>
        {#if subpath !== "health_check"}
          {#if canCreateEntry}
            <Button
              outline
              color="success"
              size="sm"
              title={$_("create_entry")}
              class="justify-contnet-center text-center py-0 px-1"
              on:click={handleCreateEntryModal}
            >
              <Icon name="file-plus" />
            </Button>
          {/if}
          {#if canCreateFolder && [ResourceType.space, ResourceType.folder].includes(resource_type) && !managementEntities.some( (m) => `${space_name}/${subpath}`.endsWith(m) )}
            <Button
              outline
              color="success"
              size="sm"
              title={$_("create_folder")}
              class="justify-contnet-center text-center py-0 px-1"
              on:click={() => {
                entryType = "folder";
                new_resource_type = ResourceType.folder;
                selectedSchema = "folder_rendering";
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
    </Nav>
  </div>

  <div
    class="px-1 tab-content"
    style="height: calc(100% - {header_height}px); overflow: hidden auto;"
    transition:fade={{ delay: 25 }}
  >
    <div class="tab-pane" class:active={tab_option === "list"}>
      <ListView
        {space_name}
        {subpath}
        folderColumns={entry?.payload?.body?.index_attributes ?? null}
        sort_by={entry?.payload?.body?.sort_by ?? null}
        sort_order={entry?.payload?.body?.sort_order ?? null}
      />
    </div>
    <div class="tab-pane" class:active={tab_option === "source"}>
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
                <textarea value={entry.payload.body.toString()} disabled />
              {:else if entry.payload.content_type === ContentType.markdown}
                {@html marked(entry.payload.body.toString())}
              {:else if entry.payload.content_type === ContentType.json}
                <Prism code={entry.payload.body} />
              {/if}
            </TabPane>
          {/if}
          <TabPane tabId="table" tab="Table" active={!isContentPreviewable}
            ><Table2Cols
              entry={{ "Resource type": resource_type, ...entry }}
            /></TabPane
          >
          <TabPane tabId="form" tab="Raw"><Prism code={entry} /></TabPane>
        </TabContent>
      </div>
    </div>
    <div class="tab-pane" class:active={tab_option === "edit_meta"}>
      <div
        class="px-1 pb-1 h-100"
        style="text-align: left; direction: ltr; overflow: hidden auto;"
      >
        {#if resource_type === ResourceType.ticket}
          <TicketEntryRenderer {space_name} {subpath} bind:entry />
        {:else if resource_type === ResourceType.user}
          <UserEntryRenderer
            {space_name}
            {subpath}
            bind:entry
            bind:errorContent
          />
        {/if}
        <JSONEditor
          bind:this={jseMetaRef}
          bind:content={jseMeta}
          bind:validator={validatorMeta}
          onRenderMenu={handleRenderMenu}
          mode={Mode.text}
        />
        {#if errorContent}
          <h3 class="mt-3">Error:</h3>
          <Prism bind:code={errorContent} />
        {/if}
      </div>
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
              />
            {/if}
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
          {#if entry.payload.content_type === "json" && typeof jseContent === "object" && jseContent !== null}
            <JSONEditor
              bind:this={jseContentRef}
              bind:content={jseContent}
              bind:validator={validatorContent}
              onRenderMenu={handleRenderMenu}
              mode={Mode.text}
            />
          {:else}
            <ContentEditor
              {space_name}
              {subpath}
              {handleSave}
              content_type={entry.payload.content_type}
              body={entry.payload.body}
              bind:jseContent
            />
          {/if}
          {#if errorContent}
            <h3 class="mt-3">Error:</h3>
            <Prism bind:code={errorContent} />
          {/if}
        </div>
      </div>
      {#if schema && jseContent?.json}
        <div class="tab-pane" class:active={tab_option === "edit_content_form"}>
          <div class="d-flex justify-content-end my-1">
            <Button on:click={handleSave}>Save</Button>
          </div>
          {#if resource_type === ResourceType.schema}
            <SchemaEditor bind:content={jseContent} />
          {:else if resource_type === ResourceType.content && schema_name === "configuration"}
            <ConfigEditor entries={jseContent.json.items} />
          {:else if resource_type === ResourceType.content && schema_name === "translation"}
            <TranslationEditor
              bind:entries={jseContent.json.items}
              columns={Object.keys(schema.properties.items.items.properties)}
            />
          {:else}
            <div class="px-1 pb-1 h-100">
              <SchemaForm
                bind:ref={schemaFormRefContent}
                {schema}
                bind:data={jseContent.json}
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
            {#if ["meta_schema"].includes(entry.shortname)}
              <WorkflowRenderer
                shortname={entry.shortname}
                workflowContent={entry?.payload?.body}
              />
            {:else}
              <PlantUML
                shortname={entry.shortname}
                properties={entry.payload.body.properties}
              />
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
    <h4 class="alert-heading text-capitalize">
      Failed to load the entry, please check its existence or try again.
    </h4>
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
