import {_} from "@/i18n";
import {Dmart, QueryType, SortyType} from "@edraj/tsdmart";
import {getSpaces} from "@/lib/dmart_services";
import {get} from "svelte/store";


/**
 * Utility functions for ListView components
 */

/**
 * Extracts value from nested data object using path array
 */
export function getValueByPath(path: string[], data: any, type: string): string {
    if (data === null) {
        return get(_)("not_applicable");
    }
    if (path.length == 1 && path[0].length > 0 && typeof(data) === "object" && path[0] in data) {
        if (type == "json") return JSON.stringify(data[path[0]], undefined, 1);
        else return data[path[0]];
    }
    if (path.length > 1 && path[0].length > 0 && path[0] in data) {
        return getValueByPath(path.slice(1), data[path[0]], type);
    }
    return get(_)("not_applicable");
}

/**
 * Calculates the number of pages for pagination
 */
export function calculateNumberOfPages(total: number, rowsPerPage: number): number {
    return Math.ceil(total / rowsPerPage);
}

/**
 * Stores rows per page setting in localStorage
 */
export function storeRowsPerPageSetting(rowsPerPage: number): void {
    if (typeof localStorage !== 'undefined') {
        localStorage.setItem("rowPerPage", rowsPerPage.toString());
    }
}

/**
 * Gets rows per page setting from localStorage
 */
export function getRowsPerPageSetting(): number {
    return parseInt(typeof localStorage !== 'undefined' && localStorage.getItem("rowPerPage")) || 15;
}


/**
 * Normalizes subpath for folder navigation
 */
export function normalizeSubpath(recordSubpath: string, recordShortname: string, currentSubpath: string): string {
    let _subpath = `${recordSubpath}/${recordShortname}`.replace(/\/+/g, "/");

    if (_subpath.length > 0 && currentSubpath[0] === "/") {
        _subpath = _subpath.substring(1);
    }
    if (_subpath.length > 0 && _subpath[_subpath.length - 1] === "/") {
        _subpath = _subpath.slice(0, -1);
    }

    return _subpath.replaceAll("/", "-");
}

/**
 * Filters request headers by removing blacklisted items
 */
export function filterRequestHeaders(headers: any): any {
    const blacklist = ["sec", "content-type", "accept", "host", "connection"];
    
    return Object.keys(headers).reduce(
        (acc, key) =>
            blacklist.some((item) => key.includes(item))
                ? acc
                : {
                    ...acc,
                    [key]: headers[key],
                },
        {}
    );
}

/**
 * Builds query object for data fetching
 */
export function buildQueryObject(params: {
    shortname?: string;
    type: QueryType;
    space_name: string;
    subpath: string;
    exact_subpath: boolean;
    numberRowsPerPage: number;
    stringSortBy: string;
    stringSortOrder: string;
    numberActivePage: number;
    search: string;
    scope: string;
    requestExtra?: any;
}): any {
    return {
        filter_shortnames: params.shortname ? [params.shortname] : [],
        type: params.type,
        space_name: params.space_name,
        subpath: params.subpath,
        exact_subpath: params.exact_subpath,
        limit: params.numberRowsPerPage,
        sort_by: params.stringSortBy.toString(),
        sort_type: SortyType[params.stringSortOrder],
        offset: params.numberRowsPerPage * (params.numberActivePage - 1),
        search: params.search.trim(),
        ...params.requestExtra,
        retrieve_json_payload: true
    };
}

/**
 * Applies folder hiding logic for root subpath
 */
export async function applyFolderHiding(search: string, subpath: string, space_name: string, spaces: any[]): Promise<string> {
    if (subpath !== "/") {
        return search;
    }

    if (spaces === null || spaces.length === 0) {
        await getSpaces();
    }

    const currentSpace = spaces.find((e) => e.shortname === space_name);
    const hideFolders = currentSpace?.attributes?.hide_folders;

    if (hideFolders?.length) {
        return search + ` -@shortname:${hideFolders.join('|')}`;
    }

    return search;
}

/**
 * Fetches page records with all the necessary logic
 */
export async function fetchPageRecords(params: {
    searchListView: string;
    subpath: string;
    spaces: any[];
    space_name: string;
    shortname?: string;
    type: QueryType;
    exact_subpath: boolean;
    objectDatatable: any;
    scope: string;
    requestExtra?: any;
}): Promise<{ total: number; records: any[] }> {
    let _search = await applyFolderHiding(
        params.searchListView,
        params.subpath,
        params.space_name,
        params.spaces
    );

    const queryObject = buildQueryObject({
        shortname: params.shortname,
        type: params.type,
        space_name: params.space_name,
        subpath: params.subpath,
        exact_subpath: params.exact_subpath,
        numberRowsPerPage: params.objectDatatable.numberRowsPerPage,
        stringSortBy: params.objectDatatable.stringSortBy,
        stringSortOrder: params.objectDatatable.stringSortOrder,
        numberActivePage: params.objectDatatable.numberActivePage,
        search: _search,
        scope: params.scope,
        requestExtra: params.requestExtra
    });

    const resp = await Dmart.query(queryObject, params.scope);

    return {
        total: resp.attributes.total,
        records: resp.records
    };
}