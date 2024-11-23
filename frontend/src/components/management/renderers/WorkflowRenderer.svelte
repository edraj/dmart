<script lang="ts">
  import { encode } from "plantuml-encoder";
  import {jsonTOplantUML} from "@/utils/renderer/workflowRendererUtils";

  let { shortname, workflowContent } : {
    shortname: string,
    workflowContent: string
  } = $props();

  let currentDiagram = {
    name: shortname,
    content: jsonTOplantUML(workflowContent),
    encodedContent: function () {
      return encode(this.content);
    },
  };
</script>


<div
  class="px-1 pb-1 h-100"
  style="text-align: left; direction: ltr; overflow: hidden auto;"
>
  <div class="preview">
    <a
      href={"https://www.plantuml.com/plantuml/svg/" + currentDiagram.encodedContent()}
      download="{shortname}.svg">
      <img
        src={"https://www.plantuml.com/plantuml/svg/" + currentDiagram.encodedContent()}
        alt={shortname}
      />
    </a>
  </div>
</div>


<style>
  .preview {
    width: 100%;
    text-align: center;
  }
</style>
