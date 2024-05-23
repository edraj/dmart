<!-- routify:meta reset -->
<script lang="ts">
    import {
        Row,
        Col,
        Card,
        CardBody,
    } from 'sveltestrap';
    import {url} from "@roxi/routify";
    import Header from "@/components/Header.svelte";
    import Footer from "@/components/Footer.svelte";

    const docFiles = [
        'index.md',
        'Installation.md',
        'Concepts.md',
        'Data-Organization.md',
        'Tools.md',
     'Examples.md',
         'Automated-Testing.md',
        'Dmart-Clients.md',  
        'Use-Cases.md',
        'Roadmap.md'
    ];

    let selectedIndex = docFiles.findIndex(file => `/docs/${file.replace('.md', '').replace('index','')}`===window.location.pathname );
</script>

<style>
    @import "prismjs/themes/prism.css";
    @import "prismjs/themes/prism-coy.css";
</style>


<Header />

<div>
<Row class="d-flex" style="height: 90vh;padding: 0px!important;" >
  <Col sm="2" style="border-right: solid #cecece;height:92vh;overflow-y: auto; padding: 0px!important;">
    <div class="d-flex bg-light">
      <ul class="nav nav-pills flex-column px-2" style="height:92vh;width: 100%;padding-top: 16px;">
        {#key $url}
          {#each docFiles as file, index}
            <!-- svelte-ignore a11y-no-noninteractive-element-interactions a11y-click-events-have-key-events -->
            <li
              on:click={()=> selectedIndex = index}
              class={
                file===docFiles[selectedIndex]
                ? "nav-item selected" : "nav-item"
              }>
              <a href="/docs/{file.replace('.md', '').replace('index','')}" class="nav-link link-dark">
                {file.replaceAll('-', ' ').replace('.md', '').replace('index','Why Dmart ?')}
              </a>
            </li>
            <hr class="p-0 m-0">
          {/each}
        {/key}
      </ul>
      <style>
        .selected {
            background-color: #e5e5e5;
        }
      </style>
    </div>
  </Col>
  <Col sm="10"  style="padding-right: 1.5rem; padding-top: 1rem;">
    <Card class="px-4" style="overflow-y: auto; height:88vh">
      <CardBody>
        <slot/>
      </CardBody>
    </Card>
  </Col>
</Row>
</div>
<div class="fixed-bottom">
  <Footer />
</div>

