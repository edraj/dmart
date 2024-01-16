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
      request, check_existing, passwordRegExp, passwordWrongExp,
  } from "@/dmart";
  import {
    Form,
    FormGroup,
    Button,
    Label,
    Input,
    Nav,
    ButtonGroup, TabPane, TabContent,
  } from "sveltestrap";
  import Icon from "../../Icon.svelte";
  import { _ } from "@/i18n";
  import ListView from "../ListView.svelte";
  import Prism from "../../Prism.svelte";
  import {
    JSONEditor,
    createAjvValidator,
    Validator,
    Mode,
  } from "svelte-jsoneditor";
  import { status_line } from "@/stores/management/status_line";
  import { timeAgo } from "@/utils/timeago";
  import { showToast, Level } from "@/utils/toast";
  import { faSave } from "@fortawesome/free-regular-svg-icons";
  import "bootstrap";
  import { isDeepEqual, removeEmpty } from "@/utils/compare";
  import metaUserSchema from "@/validations/meta.user.json";
  import checkAccess from "@/utils/checkAccess";
  import { fade } from "svelte/transition";
  import BreadCrumbLite from "@/components/management/BreadCrumbLite.svelte";
  import { toast } from "@zerodevx/svelte-toast";
  import ToastActionComponent from "@/components/management/ToastActionComponent.svelte";
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

  let tab_option = resource_type === ResourceType.folder ? "list" : "view";

  let contentMeta: any = { json: {}, text: undefined };
  let validatorMeta: Validator = createAjvValidator({ schema: metaUserSchema });
  let oldContentMeta = { json: entry || {}, text: undefined };

  let contentContent = { json: {}, text: undefined };
  let oldContentContent = { json: {}, text: undefined };
  let validatorContent: Validator = createAjvValidator({ schema: {} });

  onDestroy(() => status_line.set(""));
  status_line.set(
    `<small>Last updated: <strong>${timeAgo(
      new Date(entry.updated_at)
    )}</strong><br/>Attachments: <strong>${
      Object.keys(entry.attachments).length
    }</strong></small>`
  );

  let user: any = { displayname: { ar: "", en: "", kd: "" } };

  onMount(async () => {
    user = {
      ...user,
      email: entry?.email,
      msisdn: entry?.msisdn,
      password: "",
      is_email_verified: entry.is_email_verified,
      is_msisdn_verified: entry.is_msisdn_verified,
      force_password_change: entry.force_password_change,
    };
    if (entry.displayname) {
      user.displayname = entry.displayname;
    }

    const cpy = structuredClone(entry);

    if (contentContent === null) {
      contentContent = { json: {}, text: undefined };
    }
    contentContent.json = cpy?.payload?.body ?? {};

    delete cpy?.payload?.body;
    delete cpy?.attachments;
    contentMeta.json = cpy;

    contentContent = structuredClone(contentContent);
    oldContentContent = structuredClone(contentContent);
    contentMeta = structuredClone(contentMeta);
    oldContentMeta = structuredClone(contentMeta);
  });

  let schemaFormRef;
  let errorContent = null;
  async function handleSave() {
    errorContent = null;
    const oldMeta = oldContentMeta.json
        ? structuredClone(oldContentMeta.json)
        : JSON.parse(oldContentMeta.text);
    const meta = contentMeta.json
      ? structuredClone(contentMeta.json)
      : JSON.parse(contentMeta.text);
    const data = contentContent.json
      ? structuredClone(contentContent.json)
      : JSON.parse(contentContent.text);

      if (oldMeta.email !==  meta.email){
          const emailStatus: any = await check_existing("email", user.email);
          if (!emailStatus.attributes.unique){
              showToast(Level.warn,"Email already exists!");
              return;
          }
      }

      if (oldMeta.msisdn !==  meta.msisdn){
          const msisdnStatus: any = await check_existing("msisdn", user.msisdn);
          if (!msisdnStatus.attributes.unique){
              showToast(Level.warn,"MSISDN already exists!");
              return;
          }
      }

    if (meta.password.startsWith("$2b$12$") || meta.password == "") {
      delete meta.password;
    } else {
      if (!passwordRegExp.test(meta.password)){
          showToast(Level.warn, passwordWrongExp);
          return;
      }
    }
    const attributes = {
      ...meta,
    };
    if (Object.keys(data)) {
      attributes.payload = attributes.payload || {};
      attributes.payload.body = data;
    }
    const response = await request({
      space_name: space_name,
      request_type: RequestType.update,
      records: [
        {
          resource_type,
          shortname: entry.shortname,
          subpath,
          attributes,
        },
      ],
    });
    if (response.status == Status.success) {
      showToast(Level.info);
      oldContentMeta = structuredClone(contentMeta);
      oldContentContent = structuredClone(contentContent);

      if (attributes.shortname !== entry.shortname) {
        const moveAttrb = {
          src_subpath: subpath,
          src_shortname: entry.shortname,
          dest_subpath: subpath,
          dest_shortname: attributes.shortname,
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
      if (schema_data.status == "success" && schema_data.records.length > 0) {
        schema = schema_data.records[0].attributes["payload"].body;
        cleanUpSchema(schema.properties);

        try {
          validatorContent = createAjvValidator({ schema });
        } catch (error) {
          const name = schema_data.records[0].shortname;
          validatorContent = createAjvValidator({ schema: {} });
          toast.push({
            component: {
              src: ToastActionComponent,
              props: {
                level: Level.warn,
                message: `The schema ${name} is corrupted!`,
                action: () => {
                  $goto(
                    "/management/content/[space_name]/[subpath]/[shortname]/[resource_type]",
                    {
                      space_name,
                      subpath: "/schema",
                      shortname: entry.payload.schema_shortname,
                      resource_type: "schema",
                    }
                  );
                },
              },
            },
            initial: 0,
            dismissable: false,
          });
        }
      }
    } else {
      schema = null;
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

  onDestroy(() => {
    history.replaceState;
    return false;
  });

  function beforeUnload(event) {
    if (
      !isDeepEqual(removeEmpty(contentMeta), removeEmpty(oldContentMeta)) &&
      !isDeepEqual(removeEmpty(contentContent), removeEmpty(oldContentContent))
    ) {
      event.preventDefault();
      if (
        confirm("You have unsaved changes, do you want to leave ?") === false
      ) {
        return false;
      }
    }
  }

  async function handleUserSubmit(e) {
    e.preventDefault();
    const oldMeta = oldContentMeta.json
        ? structuredClone(oldContentMeta.json)
        : JSON.parse(oldContentMeta.text);

    if (oldMeta.email !==  user.email){
        const emailStatus: any = await check_existing("email", user.email);
        if (!emailStatus.attributes.unique){
            showToast(Level.warn,"Email already exists!");
            return;
        }
    }

    if (oldMeta.msisdn !==  user.msisdn){
        const msisdnStatus: any = await check_existing("msisdn", user.msisdn);
        if (!msisdnStatus.attributes.unique){
            showToast(Level.warn,"MSISDN already exists!");
            return;
        }
    }

    if (user.password === "") {
      delete user.password;
    } else {
      if (!passwordRegExp.test(user.password)){
          showToast(Level.warn, passwordWrongExp);
          return;
      }
    }

    const response = await request({
      space_name: space_name,
      request_type: RequestType.update,
      records: [
        {
          resource_type,
          shortname: entry.shortname,
          subpath,
          attributes: user,
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

  $: user && contentMeta &&
    (() => {
      if (contentMeta.text){
          contentMeta.json = JSON.parse(contentMeta.text);
          contentMeta.text = undefined;
      }
      const meta = structuredClone(contentMeta.json);

      contentMeta.json = { ...meta, ...user };
      meta.displayname = {
        ...meta.displayname,
        ...user.displayname,
      };
      contentMeta.text = undefined;
      contentMeta = structuredClone(contentMeta);
    })()

  $: {
    contentContent = structuredClone(contentContent);
  }
</script>

<svelte:window on:beforeunload={beforeUnload} />

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

  {#if canUpdate}
    <div class="tab-pane" class:active={tab_option === "edit_meta"}>
      <div
        class="px-1 pb-1 h-100"
        style="text-align: left; direction: ltr; overflow: hidden auto;"
      >
        <Form
          class="d-flex flex-column px-5 mt-5 mb-5"
          on:submit={handleUserSubmit}
        >
          <div class="row">
            <FormGroup class="col-4">
              <Label>Email</Label>
              <Input
                style="width: 100% !important"
                bind:value={user.email}
                class="w-25"
                type="email"
                name="email"
                placeholder="Email..."
                autocomplete="off"
              />
            </FormGroup>
            <FormGroup class="col-4">
              <Label>MSISDN</Label>
              <Input
                style="width: 100% !important"
                bind:value={user.msisdn}
                class="w-25"
                type="text"
                name="msisdn"
                placeholder="MSISDN..."
                autocomplete="off"
              />
            </FormGroup>
            <FormGroup class="col-4">
              <Label>Password</Label>
              <Input
                style="width: 100% !important"
                bind:value={user.password}
                class="w-25"
                type="password"
                name="password"
                placeholder="password..."
                minlength={8}
                maxlength={24}
                pattern={"^(?=.*d)(?=.*[A-Z])[a-zA-Zd_#@%*-!?$^]{8,24}$"}
                autocomplete="off"
              />
            </FormGroup>
          </div>
          <div class="row">
            <FormGroup class="col-4">
              <Label>English Displayname</Label>
              <Input
                style="width: 100% !important"
                bind:value={user.displayname.en}
                class="w-25"
                type="text"
                name="displayname_en"
                placeholder="English Displayname..."
              />
            </FormGroup>
            <FormGroup class="col-4">
              <Label>Arabic Displayname</Label>
              <Input
                style="width: 100% !important"
                bind:value={user.displayname.ar}
                class="w-25"
                type="text"
                name="displayname_ar"
                placeholder="Arabic Displayname..."
              />
            </FormGroup>
            <FormGroup class="col-4">
              <Label>Kurdish Displayname</Label>
              <Input
                style="width: 100% !important"
                bind:value={user.displayname.kd}
                class="w-25"
                type="text"
                name="displayname_kd"
                placeholder="Kurdish Displayname..."
              />
            </FormGroup>
          </div>
          <div class="row">
            <FormGroup class="col-4">
              <Input
                name="is_email_verified"
                bind:checked={user.is_email_verified}
                type="checkbox"
                label="Is Email Verified"
              />
            </FormGroup>
            <FormGroup class="col-4">
              <Input
                name="is_msisdn_verified"
                bind:checked={user.is_msisdn_verified}
                type="checkbox"
                label="Is MSISDN Verified"
              />
            </FormGroup>
            <FormGroup class="col-4">
              <Input
                name="force_password_change"
                bind:checked={user.force_password_change}
                type="checkbox"
                label="Force Password Change"
              />
            </FormGroup>
          </div>
          <Button color="primary" style="width: 25% !important" type="submit"
            >Save</Button
          >
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
    </div>
    {#if entry.payload}
      <div class="tab-pane" class:active={tab_option === "edit_content"}>
        <div
          class="px-1 pb-1 h-100"
          style="text-align: left; direction: ltr; overflow: hidden auto;"
        >
          <JSONEditor
            bind:content={contentContent}
            onRenderMenu={handleRenderMenu}
            mode={Mode.text}
            bind:validator={validatorContent}
          />

          {#if errorContent}
            <h3 class="mt-3">Error:</h3>
            <Prism bind:code={errorContent} />
          {/if}
        </div>
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
    {/if}
  {/if}

  <div class="tab-pane" class:active={tab_option === "history"}>
    {#key tab_option}
      <HistoryListView
        {space_name}
        {subpath}
        type={QueryType.history}
        shortname={entry.shortname}
      />
    {/key}
    <!--History subpath="{entry.subpath}" shortname="{entry.shortname}" /-->
  </div>
  <div class="tab-pane" class:active={tab_option === "attachments"}>
    <Attachments
      {space_name}
      {resource_type}
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
</style>
