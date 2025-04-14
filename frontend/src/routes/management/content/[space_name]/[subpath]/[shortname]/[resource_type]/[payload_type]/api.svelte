<script lang="ts">
  import { faSave } from "@fortawesome/free-regular-svg-icons";
  import axios from "axios";
  axios.defaults.withCredentials = true;
  import { website } from "@/config";
  import {
      Col,
      Container,
      Row,
      Button,
      Modal,
      Nav,
      ButtonGroup, ModalHeader,
  } from "sveltestrap";
  import { params } from "@roxi/routify";
  import {
    retrieve_entry,
    ResourceType,
    type ApiResponse,
    type ResponseEntry,
    RequestType,
    request,
    QueryType,
    Status,
  } from "@/dmart";
  import {
    JSONEditor,
    type JSONContent,
    Mode,
    type Validator,
    createAjvValidator,
  } from "svelte-jsoneditor";
  import Prism from "@/components/Prism.svelte";
  import { _ } from "@/i18n";
  import Icon from "@/components/Icon.svelte";
  import {checkAccessv2} from "@/utils/checkAccess";
  import { Level, showToast } from "@/utils/toast";
  import Attachments from "@/components/management/Attachments.svelte";
  import HistoryListView from "@/components/management/HistoryListView.svelte";
  import BreadCrumbLite from "@/components/management/BreadCrumbLite.svelte";
  import { fade } from "svelte/transition";
  import metaContentSchema from "@/validations/meta.content.json";

  let space_name = $params.space_name;
  let subpath = $params.subpath;
  const resource_type = ResourceType.content;

  let tab_option = "view";

  const canUpdate = checkAccessv2("update", space_name, subpath, resource_type);
  const canDelete = checkAccessv2("delete", space_name, subpath, resource_type);

  type Request = {
    verb: string;
    endpoint: string;
    body?: string;
  };

  let contentMeta = { json: {}, text: undefined };
  let validatorMeta: Validator = createAjvValidator({
    schema: metaContentSchema,
  });
  let oldContentMeta = { json: {}, text: undefined };

  let contentContent: any = null;
  let validator: Validator = createAjvValidator({ schema: {} });
  let entryContent: any;

  let errorContent = null;
  async function handleSave(e: Event) {
    e.preventDefault();
    // if (!isSchemaValidated) {
    //   alert("The content does is not validated agains the schema");
    //   return;
    // }
    errorContent = null;

    const x = contentMeta.json
      ? {...contentMeta.json}
      : JSON.parse(contentMeta.text);

    let data: any = {...x};
    if (entry?.payload) {
      if (entry?.payload?.content_type === "json") {
        const y = contentContent.json
          ? {...contentContent.json}
          : JSON.parse(contentContent.text);
        if (data.payload) {
          data.payload.body = y;
        }
      } else {
        data.payload.body = contentContent;
      }
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
    } else {
      errorContent = response;
      showToast(Level.warn);
    }
  }

  const headers: { [key: string]: string } = {
    "Content-type": "application/json",
  };

  let curl = "";
  function generateCURL(request: Request) {
    return (
      `curl -X ${request.verb} '${website.backend}/${request.endpoint}'`.replaceAll(
        "//",
        "/"
      ) +
      (request.verb == "post"
        ? "\n-H 'Content-Type: application/json'\n" +
          `-d '${JSON.stringify(
            (request_je.get()).json.request_body,
            undefined,
            2
          )}'`
        : "")
    );
  }

  async function handleDelete() {
    if (
      confirm(`Are you sure want to delete ${entry.shortname} entry`) === false
    ) {
      return;
    }

    let targetSubpath: string = $params.subpath;

    const request_body = {
      space_name: space_name,
      request_type: RequestType.delete,
      records: [
        {
          resource_type,
          shortname: entry.shortname,
          subpath: targetSubpath || "/",
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

  function handleRenderMenuJE(items: any, _context: any) {
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

  let isCurlOpen = false;
  async function toggleCurl() {
    if (!isCurlOpen) {
      const request = await retrieve_request();
      curl = generateCURL(request);
    }
    isCurlOpen = !isCurlOpen;
  }

  let entry: ResponseEntry;
  async function retrieve_request(): Promise<Request> {
    const data = await retrieve_entry(
      ResourceType.content,
      space_name,
      $params.subpath.replaceAll("-", "/"),
      $params.shortname,
      true,
      true
    );
    entry = data;

    const cpy = structuredClone(entry);
    if (entry?.payload?.content_type === "json") {
      if (contentContent === null) {
        contentContent = { json: {}, text: undefined };
      }
      contentContent.json = cpy?.payload?.body ?? {};
      contentContent = structuredClone(contentContent);
    } else {
      contentContent = cpy?.payload?.body;
    }
    delete cpy?.payload?.body;
    delete cpy?.attachments;

    contentMeta.json = cpy;
    contentMeta = structuredClone(contentMeta);
    oldContentMeta = structuredClone(contentMeta);

    if (data.payload.body as Record<string, any>) {
      return {
        verb: data.payload.body["verb"] as string,
        endpoint: data.payload.body["end_point"]
          .replace(/^\//, "")
          .replace(/\/$/, "")
          .replaceAll(/\/+/g, "/"),
        body: data.payload.body["request_body"],
      };
    }
  }

  let request_je: any;
  let response_je: any;
  async function call_api(request: Request) {
    curl = generateCURL(request);
    const { verb, endpoint } = request;
    const url = `${website.backend}/${endpoint}`.replaceAll("//", "/");
    try {
      let response: any = { data: {} };
      if (verb === "post") {
        response = await axios.post<ApiResponse>(
          url,
          JSON.stringify((request_je.get()).json.request_body),
          { headers }
        );
      } else if (verb === "get") {
        response = await axios.get<ApiResponse>(url);
      }
      response_je.set({ json: response.data });
    } catch (error) {
      if (error?.response?.data) {
        response_je.set({ json: error.response.data });
      } else {
        response_je.set({ json: { error: "Empty response!" } });
      }
    }
  }

  let header_height: number;
</script>

<Modal
  body
  header="Curl command"
  isOpen={isCurlOpen}
  toggle={toggleCurl}
  size="lg"
>
  <ModalHeader toggle={toggleCurl}/>
  <div class="modal-header">
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <button type="button" onclick={toggleCurl} class="btn-close" aria-label="Close">
    </button>
  </div>
  <Prism language="bash" code={curl} />
</Modal>

{#if $params.space_name && $params.subpath && $params.shortname}
  {#await retrieve_request()}
    <!--h6 transition:fade >Loading ... @{$params.space_name}/{$params.subpath}</h6-->
  {:then request}
    <div
      bind:clientHeight={header_height}
      class="pt-3 pb-2 px-2"
      transition:fade={{ delay: 25 }}
    >
      <div class="d-flex justify-content-end w-100">
        <BreadCrumbLite
          {space_name}
          {subpath}
          {resource_type}
          schema_name="api"
          shortname={$params.shortname}
        />
        <ButtonGroup size="sm" class="ms-auto align-items-center">
          <span class="ps-2 pe-1"> {$_("views")} </span>
          <Button
            outline
            color="success"
            size="sm"
            class="justify-content-center text-center py-0 px-1"
            active={"view" === tab_option}
            title={$_("view")}
            onclick={() => (tab_option = "view")}
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
              onclick={() => (tab_option = "edit_meta")}
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
                onclick={() => (tab_option = "edit_content")}
              >
                <Icon name="pencil" />
              </Button>
              <Button
                outline
                color="success"
                size="sm"
                class="justify-content-center text-center py-0 px-1"
                active={"api_call" === tab_option}
                title={$_("edit") + " payload"}
                onclick={() => (tab_option = "api_call")}
              >
                <Icon name="send" />
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
            onclick={() => (tab_option = "attachments")}
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
            onclick={() => (tab_option = "history")}
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
              onclick={handleDelete}
              class="justify-content-center text-center py-0 px-1"
            >
              <Icon name="trash" />
            </Button>
          {/if}
        </ButtonGroup>
      </div>
    </div>

    <div
      class="tab-content"
      style="overflow: hidden auto;"
      transition:fade={{ delay: 25 }}
    >
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
              onRenderMenu={handleRenderMenuJE}
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
            {#if entry.payload.content_type === "json" && typeof contentContent === "object" && contentContent !== null}
              <JSONEditor
                mode={Mode.text}
                bind:content={contentContent}
                bind:validator
                onRenderMenu={handleRenderMenuJE}
              />
            {/if}

            {#if errorContent}
              <h3 class="mt-3">Error:</h3>
              <Prism bind:code={errorContent} />
            {/if}
          </div>
        </div>
        <div class="tab-pane" class:active={tab_option === "api_call"}>

            <Row>
              <Col>
                <p style="margin: 0px">
                  <b>Endpoint:</b> <code>{request.endpoint}</code> - 
                  <b>Verb:</b> <code>{request.verb}</code>
                </p>
              </Col>
              <Col class="d-flex justify-content-end">
                <Button class="mx-1" onclick={toggleCurl}>Show curl</Button>
                <Button
                  color="success"
                  onclick={async () => await call_api(request)}>Call</Button
                >
              </Col>
            </Row>
            <Row>
              <Col
                ><b> Request </b><JSONEditor
                  onRenderMenu={handleRenderMenu}
                  mode={Mode.text}
                  bind:this={request_je}
                  content={{ json: entry.payload.body || {} }}
                /></Col
              >
              <Col
                ><b> Response </b>
                <JSONEditor
                  onRenderMenu={handleRenderMenu}
                  mode={Mode.text}
                  bind:this={response_je}
                  content={{ text: "{}" }}
                  readOnly={true}
                /></Col
              >
            </Row>

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
          {resource_type}
          {subpath}
          parent_shortname={entry.shortname}
          attachments={Object.values(entry.attachments)}
          refreshEntry={retrieve_request}
        />
      </div>
    </div>
  {:catch error}
    <p style="color: red">{error.message}</p>
  {/await}
{:else}
  <h4>We shouldn't be here ...</h4>
  <pre>{JSON.stringify($params)}</pre>
{/if}
