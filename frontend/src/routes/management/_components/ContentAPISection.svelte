<script>
  import { Col, Container, Row, Button } from "sveltestrap";
  import { website } from "../../../config";
  import { dmartRequest } from "../../../dmart.js";
  import ContentJsonEditor from "./ContentJsonEditor.svelte";

  export let input;
  export let request;

  let inputContent = {
    json: input,
    text: undefined,
  };
  let outputContent = {
    json: {},
    text: undefined,
  };
  let curl = "";
  function generateCURL(endpoint, body) {
    let curl = "curl\n";
    curl += `-X ${request.verb}\n`;
    curl += "-H 'Accept: */*'\n";
    curl += "-H 'Content-Type: application/json'\n";
    curl += `-d '${JSON.stringify(body, undefined, 4)}'\n`;
    curl += `"${website.backend}/${endpoint}"`;
    return curl;
  }

  async function handleSave() {
    const body = inputContent.json
      ? { ...inputContent.json }
      : JSON.parse(inputContent.text);
    const endpoint = request.end_point.startsWith("/")
      ? request.end_point.slice(1, request.end_point.length)
      : request.end_point;
    curl = generateCURL(endpoint, body);
    outputContent.json = await dmartRequest(endpoint, body);
  }
</script>

<Container>
  <Row class="my-3">
    <Col class="d-flex justify-content-end"
      ><Button on:click={handleSave}>Execute</Button></Col
    >
  </Row>
  <Row>
    <Col><ContentJsonEditor bind:content={inputContent} /></Col>

    <Col><ContentJsonEditor bind:content={outputContent} readOnly={true} /></Col
    >
  </Row>
  <Row>
    <Col>
      <div class="result-text">{curl}</div>
    </Col>
  </Row>
</Container>

<style>
  .result-wrapper {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin-top: 20px;
  }

  .result-text {
    /* width: 100%; */
    /* max-width: 600px; */
    height: auto;
    padding: 20px;
    background-color: #f5f5f5;
    border-radius: 5px;
    font-family: monospace;
    white-space: pre-wrap;
    word-wrap: break-word;
    margin-bottom: 20px;
  }
</style>
