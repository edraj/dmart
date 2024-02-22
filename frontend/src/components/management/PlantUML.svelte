<script lang="ts">
import {schemaVisualizationEncoder} from "@/utils/plantUML.js";

export let shortname: string;
export let properties: any;

</script>
<a href={"https://www.plantuml.com/plantuml/svg/" +
   schemaVisualizationEncoder(properties)}
   download="{shortname}.svg"
>
  <img src={"https://www.plantuml.com/plantuml/svg/" +
       schemaVisualizationEncoder(properties)}
       alt={shortname}
  />
</a>