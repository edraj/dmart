<script lang="ts">
    import {
        Row,
        Col,
        Card,
        CardBody
    } from 'sveltestrap';

    const docFiles = [
        'index.md',
        'Attachments.md',
        'Content-Types.md',
        'Installation.md',
        'Relationships.md',
        'Subpath.md',
        'Meta-Attributes.md',
        'Schema.md',
        'Simple-Example.md',
        'Space.md',
        'Tickets.md'
    ];

    let window_height: number;
    let footer_height: number;
</script>

<style>
    @import "prismjs/themes/prism.css";
    @import "prismjs/themes/prism-coy.css";
</style>

<Row class="d-flex" style="margin-top: -1rem;height: 88vh;padding: 0px!important;" >
  <Col sm="2" style="height:88vh;overflow-y: auto; padding: 0px!important;">
    <div class="d-flex bg-light">
      <ul class="nav nav-pills flex-column" style="height:88vh;">
        {#each docFiles as file}
          <li class="nav-item">
            <a href="/docs/{file.replace('.md', '').replace('index','')}" class="nav-link link-dark">
              {file.replaceAll('-', ' ').replace('.md', '').replace('index','Why Dmart ?')}
            </a>
          </li>
        {/each}
      </ul>
    </div>
  </Col>
  <Col sm="10" style="padding: 1rem; margin-top: -1rem">
    <Card style="overflow-y: auto; height:88vh">
      <CardBody>
        <slot/>
      </CardBody>
    </Card>
  </Col>
</Row>
