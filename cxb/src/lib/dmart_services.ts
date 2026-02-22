import {type ApiQueryResponse, Dmart, type QueryRequest, QueryType, ResourceType, SortyType,} from "@edraj/tsdmart";
import {spaces} from "@/stores/management/spaces";
import {Level, showToast} from "@/utils/toast";


export async function getAvatar(shortname: string) {
    const query: QueryRequest = {
        "filter_shortnames": [],
        "type": QueryType.attachments,
        "space_name": "personal",
        "subpath": `people/${shortname}/protected/avatar`,
        "limit": 1,
        "sort_by": "shortname",
        "sort_type": SortyType.ascending,
        "offset": 0,
        "search": "@resource_type:media",
        "retrieve_json_payload": false
    }
    const results = await Dmart.query(query);

    if (results.records.length === 0) {
        return null
    }

    return Dmart.getAttachmentUrl(
        {
            resource_type: ResourceType.media,
            space_name: "personal",
            subpath: `people/${shortname}/protected/`,
            parent_shortname: "avatar",
            shortname: results.records[0].attributes.payload.body,
            ext: ''
        },
    );
}

export async function getSpaces(): Promise<ApiQueryResponse> {
    const _spaces: any = await Dmart.query({
        type: QueryType.spaces,
        space_name: "management",
        subpath: "/",
        search: "",
        limit: 100,
    });
    _spaces.records = _spaces.records.map(e => {
        if (e.attributes.ordinal === null) {
            e.attributes.ordinal = 9999;
        }
        return e;
    });
    _spaces.records.sort((a, b) => a.attributes.ordinal - b.attributes.ordinal);
    spaces.set(_spaces.records);
    return _spaces;
}

export async function getChildren(
    space_name: string,
    subpath: string,
    limit: number = 20,
    offset: number = 0,
    restrict_types: Array<ResourceType> = [],
    spaces: any = null,
    ignoreFilter = false
): Promise<ApiQueryResponse> {
    const folders = await Dmart.query({
        type: QueryType.search,
        space_name: space_name,
        subpath: subpath,
        filter_types: restrict_types,
        exact_subpath: true,
        search: "",
        limit: limit,
        offset: offset,
    });
    if (ignoreFilter == false && spaces !== null) {
        const selectedSpace = spaces.records.find(record => record.shortname === space_name);
        const hiddenFolders: string[] = selectedSpace.attributes.hide_folders;
        if (hiddenFolders) {
            folders.records = folders.records.filter(record => hiddenFolders.includes(record.shortname) === false);
        }
    }

    folders.records = folders.records.sort((leftSide, rightSide) => {
        if (leftSide.shortname.toLowerCase() < rightSide.shortname.toLowerCase()) return -1;
        if (leftSide.shortname.toLowerCase() > rightSide.shortname.toLowerCase()) return 1;
        return 0;
    });
    return folders
}

export async function getChildrenAndSubChildren(subpathsPTR: any, spacename, base: string, _subpaths: any) {
    for (const _subpath of _subpaths.records) {
        if (_subpath.resource_type === "folder") {
            const fullPath = `${base}/${_subpath.shortname}`;
            const childSubpaths = await getChildren(spacename, fullPath, 100);
            await getChildrenAndSubChildren(subpathsPTR, spacename, fullPath, childSubpaths);
            subpathsPTR.push(fullPath);
        }
    }
}

export async function fetchWorkflows(space_name: string) {
    try {
        const result = await Dmart.query({
            search: '',
            type: QueryType.search,
            space_name,
            subpath: '/workflows'
        });
        return result.records || [];
    } catch (e) {
        showToast(Level.warn, "Failed to fetch workflows");
    }
}
