<script lang="ts">
    import { onMount } from "svelte";
    import {Col, Container, Input, Label, Row, TabContent, TabPane} from "sveltestrap";
    import {JSONEditor} from "svelte-jsoneditor";


    export let content: any = [];
    export let payload: any = {};

    let _user = {
        "is_active": true,
        "displayname": {
            "en": "",
            "ar": "",
            "ku": ""
        },
        "description": {
            "en": "",
            "ar": "",
            "ku": ""
        },
        "tags": [],
        "password": "",
        "email": "",
        "msisdn": "",
        "type": "",
        "roles": [],
        "groups": [],
        "firebase_token": "",
        "language": "",
        "is_email_verified": false,
        "is_msisdn_verified": false,
        "force_password_change": false,
    };

    let inputs = [];

    let keys = Object.keys(_user);

    onMount(() => {
        inputs = keys.map((key) => {
            return { key, value: _user[key] };
        });
    });

    $: {
        if (inputs){
            content = inputs
        }
    }

    function formatting(str){
        return (str.charAt(0).toUpperCase() + str.slice(1)).replaceAll("_", " ");
    }
</script>

<TabContent>
  <TabPane tabId="meta" tab="Meta" active>
    <Container class="mt-3">
      {#each inputs as input, index}
        {#if typeof(input.value) === "boolean"}
          <Row class="my-2">
            <Col sm="11"><Label>{formatting(input.key)}</Label></Col>
            <Col sm="1">
              <Input type="checkbox" bind:checked={input.value} />
            </Col>
          </Row>
        {:else if input.key === "displayname" || input.key === "description"}
          <Row class="my-2">
            <Col sm="12"><Label>{formatting(input.key)}</Label></Col>
            {#each Object.keys(input.value) as lang}
              <Col sm="4">
                <Input
                        type="text"
                        class="form-control"
                        bind:value={input.value[lang]}
                        placeholder={`${formatting(input.key)} (${lang})...`}
                />
              </Col>
            {/each}
          </Row>
        {:else}
          <Row class="my-3">
            <Col sm="2"><Label>{formatting(input.key)}</Label></Col>
            <Col sm="10">
              <Input bind:value={input.value} />
            </Col>
          </Row>
        {/if}
      {/each}
    </Container>
  </TabPane>
  <TabPane tabId="payload" tab="Payload">
    <JSONEditor bind:content={payload} />
  </TabPane>
</TabContent>
