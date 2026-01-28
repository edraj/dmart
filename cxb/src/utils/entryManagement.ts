import {Dmart, RequestType, ResourceType, type ResponseEntry} from "@edraj/tsdmart";
import {removeEmpty} from "@/utils/renderer/schemaEntryRenderer";
import {Level, showToast} from "@/utils/toast";
import {jsonEditorContentParser} from "@/utils/jsonEditor";

/**
 * Gets the parent subpath from a given path
 */
export function getParentSubpath(path: string): string {
    const normalizedPath = path.replace(/^\/+|\/+$/g, "");
    const parts = normalizedPath.split("/");

    if (parts.length <= 1 || (parts.length === 1 && parts[0] === "")) {
        return "/";
    }

    return "/" + parts.slice(0, -1).join("/");
}

/**
 * Handles saving entry data with proper content processing
 */
export async function saveEntry(
    jeContent: any,
    space_name: string,
    subpath: string,
    resource_type: ResourceType,
    originalJeContent?: any
): Promise<{ success: boolean; errorMessage?: string }> {
    const content = jsonEditorContentParser(jeContent);

    const shortname = content.shortname;
    delete content.uuid;
    delete content.shortname;

    if (resource_type === ResourceType.schema) {
        content.payload.body = removeEmpty(content.payload.body);
    } else if (resource_type === ResourceType.content && subpath === "workflows") {
        content.payload = {
            body: removeEmpty(jsonEditorContentParser(content.payload.body)),
            schema: 'workflow',
            content_type: "json"
        };
    }

    if (resource_type === ResourceType.user && (content.password.startsWith("$argon2id")||content.password==='')) {
        delete content.password;
    }

    if (originalJeContent) {
        const originalContent = jsonEditorContentParser(originalJeContent);
        if (originalContent.payload && originalContent.payload.body && content.payload && content.payload.body) {
            const originalKeys = Object.keys(originalContent.payload.body);
            const currentKeys = Object.keys(content.payload.body);
            const removedKeys = originalKeys.filter(key => !currentKeys.includes(key));
            removedKeys.forEach(key => {
                content.payload.body[key] = null;
            });
        }
    }

    try {
        await Dmart.request({
            space_name: space_name,
            request_type: RequestType.update,
            records: [{
                resource_type: resource_type,
                shortname: shortname,
                subpath: resource_type === ResourceType.folder ? getParentSubpath(subpath) : subpath,
                attributes: removeEmpty(content)
            }]
        });
        showToast(Level.info, `Entry has been updated successfully!`);
        return { success: true };
    } catch (error: any) {
        return { success: false, errorMessage: error.response?.data || error.message };
    }
}

/**
 * Deletes an entry
 */
export async function deleteEntry(
    entry: ResponseEntry,
    space_name: string,
    subpath: string,
    resource_type: ResourceType
): Promise<{ success: boolean; errorMessage?: string }> {
    let targetSubpath: string;
    if (resource_type === ResourceType.folder) {
        const arr = subpath.split("/");
        arr[arr.length - 1] = "";
        targetSubpath = arr.join("/");
    } else {
        targetSubpath = subpath;
    }

    try {
        await Dmart.request({
            space_name: space_name,
            request_type: RequestType.delete,
            records: [{
                resource_type: resource_type,
                shortname: entry.shortname,
                subpath: targetSubpath || '/',
                attributes: {}
            }]
        });
        showToast(Level.info, `Entry deleted successfully`);
        return { success: true };
    } catch (error: any) {
        showToast(Level.warn, `Failed to delete the entry!`);
        return { success: false, errorMessage: error.message };
    }
}

/**
 * Moves an entry to trash
 */
export async function moveEntryToTrash(
    entry: ResponseEntry,
    space_name: string,
    subpath: string,
    resource_type: ResourceType,
    userShortname: string
): Promise<{ success: boolean; errorMessage?: string }> {
    try {
        const moveResourceType = resource_type;
        const moveNewSubpath = moveResourceType === ResourceType.folder
            ? (subpath.split("/").slice(0, -1).join("-") || '/')
            : subpath;

        const moveAttrb = {
            src_space_name: space_name,
            src_subpath: moveNewSubpath,
            src_shortname: entry.shortname,
            dest_space_name: 'personal',
            dest_subpath: `/people/${userShortname}/trash/${space_name}/${moveNewSubpath}`.replaceAll('//', '/'),
            dest_shortname: entry.shortname,
        };

        await Dmart.request({
            space_name: space_name,
            request_type: RequestType.move,
            records: [
                {
                    resource_type: moveResourceType,
                    shortname: entry.shortname,
                    subpath: moveNewSubpath,
                    attributes: moveAttrb,
                },
            ],
        });
        showToast(Level.info, `Entry deleted successfully`);
        return { success: true };
    } catch (error: any) {
        showToast(Level.warn, `Failed to delete the entry!`);
        return { success: false, errorMessage: error.message };
    }
}

/**
 * Checks if the current location allows exact subpath values
 */
export function getExactSubpathValue(space_name: string, subpath: string): boolean {
    if (
        space_name === 'personal'
        && subpath.startsWith('people/')
        && subpath.endsWith('/trash')
    ) {
        return false;
    }
    return true;
}

/**
 * Gets payload schema for a given schema shortname
 */
export async function getPayloadSchema(schemaShortname: string, space_name: string): Promise<any> {
    if (schemaShortname === "folder_rendering") {
        return await Dmart.retrieveEntry({resource_type: ResourceType.schema, space_name: "management", subpath: "schema", shortname: schemaShortname, retrieve_json_payload: true, retrieve_attachments: false, validate_schema: true});
    }
    return await Dmart.retrieveEntry({resource_type: ResourceType.schema, space_name, subpath: "schema", shortname: schemaShortname, retrieve_json_payload: true, retrieve_attachments: false, validate_schema: true});
}