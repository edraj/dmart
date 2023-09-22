<script lang="ts">
  import axios from "axios";
  axios.defaults.withCredentials = true;
  import { website } from "@/config";
  import { Col, Container, Row, Button, Modal } from "sveltestrap";
  import { params } from "@roxi/routify";
  import { retrieve_entry, ResourceType, ApiResponse } from "@/dmart";
  import { JSONEditor, JSONContent, Mode } from "svelte-jsoneditor";
  import Prism from "@/components/Prism.svelte";

  type Request = {
    verb: string;
    endpoint: string;
    body?: string;
  };

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
            (request_je.get() as JSONContent).json,
            undefined,
            2
          )}'`
        : "")
    );
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

  async function retrieve_request(): Promise<Request> {
    const data = await retrieve_entry(
      ResourceType.content,
      $params.space_name,
      $params.subpath.replaceAll("-", "/"),
      $params.shortname,
      true,
      true
    );
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

  let request_je: JSONEditor;
  let response_je: JSONEditor;
  async function call_api(request: Request) {
    curl = generateCURL(request);
    const { verb, endpoint } = request;
    const url = `${website.backend}/${endpoint}`.replaceAll("//", "/");
    try {
      let response: any = { data: {} };
      if (verb === "post") {
        response = await axios.post<ApiResponse>(
          url,
          JSON.stringify((request_je.get() as JSONContent).json),
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
</script>

{#if $params.space_name && $params.subpath && $params.shortname}
  {#await retrieve_request()}
    <!--h6 transition:fade >Loading ... @{$params.space_name}/{$params.subpath}</h6-->
  {:then request}
    <Container>
      <Row class="my-3">
        <Col class="d-flex justify-content-between">
          <Col>
            <p style="margin: 0px">
              <b>{$params.subpath} / {$params.shortname}</b> - Endpoint:
              <code>{request.endpoint}</code>
              Verb: <code>{request.verb}</code>
              <Button on:click={toggleCurl}>Show curl</Button>
              <Button
                color="success"
                on:click={async () => await call_api(request)}>Call</Button
              >
            </p>
          </Col>
        </Col>
      </Row>
      <Row>
        <Col
          ><b> Request </b><br /><JSONEditor
            mode={Mode.text}
            bind:this={request_je}
            onRenderMenu={handleRenderMenu}
            content={{ json: request.body || {} }}
          /></Col
        >
        <Col
          ><b> Response </b><br />
          <JSONEditor
            mode={Mode.text}
            bind:this={response_je}
            onRenderMenu={handleRenderMenu}
            content={{ text: "{}" }}
            readOnly={true}
          /></Col
        >
      </Row>
    </Container>
  {:catch error}
    <p style="color: red">{error.message}</p>
  {/await}
{:else}
  <h4>We shouldn't be here ...</h4>
  <pre>{JSON.stringify($params)}</pre>
{/if}

<Modal
  body
  header="Curl command"
  isOpen={isCurlOpen}
  toggle={toggleCurl}
  size="lg"
>
  <Prism language="bash" code={curl} />
</Modal>
