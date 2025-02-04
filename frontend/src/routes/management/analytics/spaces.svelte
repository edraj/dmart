<script lang="ts">
    import { get_children, get_spaces } from '@/dmart';
    import { onMount } from 'svelte';

    let spaces: any = $state([]);

    async function buildSubpaths(space_name, base: string): Promise<[any, any]> {
        const _children: any = await get_children(space_name, base, 100, 0, [], null, true);

        const subpaths = [];
        for (const child of _children.records) {
            const _subpaths = {};
            if (child.resource_type !== "folder") {
                continue;
            }
            _subpaths["shortname"] = child.shortname;
            if (_subpaths["subpaths"] === undefined) {
                _subpaths["subpaths"] = [];
            }

            const [s, t] = await buildSubpaths(space_name, `${base}/${child.shortname}`);

            if (s.length) {
                _subpaths["subpaths"].push(s);
            } else {
                _subpaths["subpaths"] = t;
            }
            // if (typeof _subpaths["subpaths"] !== "number") {
            //     _subpaths["subpaths"] = _subpaths["subpaths"].filter((subpath) => Object.keys(subpath).length);
            // }

            subpaths.push(_subpaths);
        }
        return [subpaths, _children.attributes.total];
    }

    function flattenSubpaths(subpaths: any[], parentShortname: string = ""): any[] {
        let flattened = [];
        for (const subpath of subpaths) {
            if (Array.isArray(subpath)) {
                flattened = flattened.concat(flattenSubpaths(subpath, parentShortname));
            } else {
                const fullShortname = parentShortname ? `${parentShortname}/${subpath.shortname}` : subpath.shortname;
                let subpathRecords = 0;
                if (Array.isArray(subpath.subpaths)) {
                    subpathRecords = subpath.subpaths.reduce((sum, sp) => sum + (Array.isArray(sp) ? sp.length : 1), 0);
                } else {
                    subpathRecords = subpath.subpaths;
                }
                flattened.push({ ...subpath, shortname: fullShortname, subpaths: subpathRecords });
                if (Array.isArray(subpath.subpaths) && subpath.subpaths.length > 0) {
                    flattened = flattened.concat(flattenSubpaths(subpath.subpaths, fullShortname));
                }
            }
        }
        return flattened;
    }

    onMount(async () => {
        const _spaces = await get_spaces();
        for (const space of _spaces.records) {
            const [subpaths, __] = await buildSubpaths(space.shortname, "/");

            const flattenedSubpaths = flattenSubpaths(subpaths);
            const totalRecords = flattenedSubpaths.reduce((sum, subpath) => sum + subpath.subpaths, 0);

            spaces.push({
                shortname: space.shortname,
                subpaths: flattenedSubpaths,
                totalRecords
            });
        }
    });
</script>


<table class="mx-auto mt-4">
    <thead>
        <tr>
            <th>Shortname</th>
            <th>Total</th>
        </tr>
    </thead>
    <tbody>
        {#each spaces as space}
            <tr>
                <td><strong>{space.shortname}</strong></td>
                <td>{space.totalRecords}</td>
            </tr>
            {#each space.subpaths as subpath}
                <tr>
                    <!--{JSON.stringify(subpath)}-->
                    <td>{subpath.shortname}</td>
                    <td>{subpath.subpaths}</td>
                </tr>
            {/each}
        {/each}
        <tr>
            <td></td>
            <td>{spaces.reduce((sum, space) => sum + space.totalRecords, 0)}</td>
        </tr>
    </tbody>
</table>

<style>
    table {
        width: 80vw;
        border-collapse: collapse;
    }
    th, td {
        border: 1px solid #ddd;
        padding: 8px;
    }
    th {
        background-color: #f2f2f2;
        text-align: left;
    }
    tr:nth-child(even) {
        background-color: #f9f9f9;
    }
    tr:hover {
        background-color: #ddd;
    }
    strong {
        font-weight: bold;
    }
</style>