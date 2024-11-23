<script lang="ts">
    import Tags from "@/components/management/renderers/Tags.svelte";
    import Markdoc from "@markdoc/markdoc";
    import yaml from "js-yaml";
    import ListView from "@/components/management/ListView.svelte";
    import {QueryType} from "@/dmart/index.js";

    let { doc = "" } = $props();

    const config = {
        tags: {
            ListView: {
                render: "ListView",
                attributes: {
                    type: {
                        type: String,
                    },
                    space_name: {
                        type: String,
                    },
                    subpath: {
                        type: String,
                    },
                    scope: {
                        type: String,
                    },
                    is_clickable: {
                        type: Boolean,
                    },
                }
            }
        }
    };
    const components = new Map([
        ["ListView", ListView],
    ]);

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
