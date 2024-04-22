<script lang="ts">
    import Tags from "@/components/management/renderers/Tags.svelte";

    export let doc = "";
    const config = {
      tags: {
        ListView: {
              render: "ListView",
              attributes: {
                  type: {
                      type: String,
                      default: QueryType.subpath,
                  },
                  space_name: {
                      type: String, default: "myspace"
                  },
                  subpath: {
                      type: String, default: "/"
                  },
                  scope: {
                      type: String, default: "public"
                  },
                  is_clickable: {
                      type: Boolean, default: false
                  },
              }
          }
      }
    };
    const components = new Map([
        ["ListView", ListView],
    ]);
    import Markdoc from "@markdoc/markdoc";
    import yaml from "js-yaml";
    import ListView from "@/components/management/ListView.svelte";
    import {QueryType} from "@/dmart/index.js";

    export function add_frontmatter(ast, config) {
        const frontmatter = ast.attributes.frontmatter ? yaml.load(ast.attributes.frontmatter) : {};
        const markdoc = Object.assign(config?.variables?.markdoc || {}, { frontmatter });
        const variables = Object.assign(config?.variables || {}, { markdoc });
        return Object.assign(config, { variables });
    }

    const ast = Markdoc.parse(doc);
    const config_with_frontmatter = add_frontmatter(ast, config);
    const content: any = Markdoc.transform(ast, config_with_frontmatter);
</script>

<Tags children={content.children} {components}></Tags>
