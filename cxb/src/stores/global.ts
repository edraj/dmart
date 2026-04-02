import {writable} from "svelte/store";
import {ResourceType, type ResponseEntry} from "@edraj/tsdmart";

export const currentEntry = writable<{entry: ResponseEntry | null; [key: string]: any} | null>(null);
export const currentListView = writable<{fetchPageRecords: (isSetPage?: boolean, requestExtra?: {}) => Promise<void>; query?: any; [key: string]: any} | null>(null);
export const spaceChildren = writable<{
    data: Map<string, any>;
    refresh: ((spaceName: any, subpath?: string, invalidate?: boolean) => Promise<any>) | null;
}>({
    data: new Map(),
    refresh: null,
});

export const resourceTypeWithNoPayload = [
    ResourceType.role,
    ResourceType.permission,
];
export const subpathInManagementNoAction = [
    "roles",
    "permissions",
    "groups",
];

export const resourcesWithFormAndJson = [
    ResourceType.space,
    ResourceType.user,
    ResourceType.content,
    ResourceType.folder,
    ResourceType.ticket,
];

export enum InputMode {
    form = "form",
    json = "json"
}
