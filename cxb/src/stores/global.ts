import {writable} from "svelte/store";
import {ResourceType} from "@edraj/tsdmart";

export const currentEntry = writable(null);
export const currentListView = writable(null);
export const spaceChildren = writable({
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
    ResourceType.user,
    ResourceType.content,
    ResourceType.folder,
    ResourceType.ticket,
];

export enum InputMode {
    form = "form",
    json = "json"
}
