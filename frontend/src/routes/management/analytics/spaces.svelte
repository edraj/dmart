<script lang="ts">
    import { get_children, get_spaces } from '@/dmart';
    import { Card, CardBody, CardTitle, ListGroup, ListGroupItem } from 'sveltestrap';
    import { onMount } from 'svelte';
    import SubpathItem from "@/routes/management/analytics/components/SubpathItem.svelte";

    let spaces: any = $state([]);

    async function buildSubpaths(space_name, base: string): Promise<[any, any]> {
        const _children: any = await get_children(space_name, base, 100, 0, [], null, true);

        const subpaths = [];
        for (const child of _children.records) {
            const _subpaths = {};
            console.log({child}, child.resource_type === "folder");
            if (child.resource_type !== "folder") {
                continue;
            }
            _subpaths["shortname"] = child.shortname;
            if (_subpaths["subpaths"] === undefined) {
                _subpaths["subpaths"] = [];
            }

            const [s, t] = await buildSubpaths(space_name, `${base}/${child.shortname}`);
            console.log(space_name, base,{ s, t });
            if (s.length) {
                _subpaths["subpaths"].push(s);
            } else {
                _subpaths["subpaths"] = t;
            }
            console.log({_subpaths})
            // if (typeof _subpaths["subpaths"] !== "number") {
            //     _subpaths["subpaths"] = _subpaths["subpaths"].filter((subpath) => Object.keys(subpath).length);
            // }

            subpaths.push(_subpaths);
        }
        return [subpaths, _children.attributes.total];
    }

    onMount(async () => {
        const _spaces = await get_spaces();
        // for (const space of _spaces.records) {
            const [subpaths, __] = await buildSubpaths(_spaces.records[0].shortname, "/");
            spaces.push({
                shortname: _spaces.records[0].shortname,
                subpaths: subpaths,
            });
        console.log({subpaths});
        // }
    });
</script>

{#each spaces as space}
    <Card class="mb-3">
        <CardBody>
            <CardTitle tag="h5">{space.shortname}</CardTitle>
            <ListGroup flush>
                {#each space.subpaths as subpath}
                    <SubpathItem subpath={subpath} />
                {/each}
            </ListGroup>
        </CardBody>
    </Card>
{/each}

<style>
    .ms-3 {
        margin-left: 1rem;
    }
    .mb-3 {
        margin-bottom: 1rem;
    }
</style>