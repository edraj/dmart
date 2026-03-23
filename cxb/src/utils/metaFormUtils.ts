import {Dmart, RequestType, ResourceType} from "@edraj/tsdmart";

/**
 * Utility functions for Meta Form components
 */

/**
 * Validates form element and reports validity issues
 */
export function validateForm(form: HTMLFormElement): boolean {
    const isValid = form.checkValidity();

    if (!isValid) {
        form.reportValidity();
    }

    return isValid;
}

/**
 * Validates shortname format (alphanumeric and underscores only)
 */
export function validateShortname(shortname: string): { isValid: boolean; error?: string } {
    if (!shortname.match(/^[a-zA-Z0-9_]+$/)) {
        return {
            isValid: false,
            error: "Shortname can only contain alphanumeric characters, underscores."
        };
    }
    return { isValid: true };
}

/**
 * Creates default form data structure for meta forms
 */
export function createDefaultMetaFormData(formData: any): any {
    return {
        ...formData,
        shortname: formData.shortname || null,
        is_active: formData.is_active !== undefined ? formData.is_active : true,
        slug: formData.slug || null,
        displayname: {
            en: formData.displayname?.en || null,
            ar: formData.displayname?.ar || null,
            ku: formData.displayname?.ku || null
        },
        description: {
            en: formData.description?.en || null,
            ar: formData.description?.ar || null,
            ku: formData.description?.ku || null
        },
    };
}

/**
 * Builds move attributes for entry renaming/moving operations
 */
export function buildMoveAttributes(params: {
    space_name: string;
    subpath: string;
    oldShortname: string;
    newShortname: string;
    resourceType: ResourceType;
}): any {
    let newSubpath = params.resourceType === ResourceType.folder
        ? (params.subpath.split("-").slice(0, -1).join("/") || '/')
        : params.subpath;
    newSubpath = newSubpath.replaceAll("-", "/");

    return {
        src_space_name: params.space_name,
        src_subpath: newSubpath,
        src_shortname: params.oldShortname,
        dest_space_name: params.space_name,
        dest_subpath: newSubpath,
        dest_shortname: params.newShortname,
    };
}

/**
 * Performs entry move operation
 */
export async function moveEntry(params: {
    space_name: string;
    subpath: string;
    oldShortname: string;
    newShortname: string;
    resourceType: ResourceType;
}): Promise<void> {
    const moveAttribs = buildMoveAttributes(params);
    const newSubpath = moveAttribs.src_subpath;

    await Dmart.request({
        space_name: params.space_name,
        request_type: RequestType.move,
        records: [
            {
                resource_type: params.resourceType,
                shortname: params.oldShortname,
                subpath: newSubpath,
                attributes: moveAttribs,
            },
        ],
    });
}

/**
 * Generates navigation URL and payload after entry operations
 */
export function generateNavigationInfo(params: {
    space_name: string;
    subpath: string;
    shortname: string;
    resourceType: ResourceType;
}): { url: string; payload: any } {
    let url = "/management/content";
    let gotoPayload: any = {
        space_name: params.space_name,
    };

    if (params.resourceType === ResourceType.space) {
        url += '/[space_name]';
    } else {
        if (params.resourceType === ResourceType.folder) {
            url += '/[space_name]/[subpath]';
            gotoPayload = {
                ...gotoPayload,
                subpath: `${params.subpath.replaceAll("-", "/")}-${params.shortname}`,
            };
        } else {
            url += `/[space_name]/[subpath]/[shortname]/[resource_type]`;
            gotoPayload = {
                ...gotoPayload,
                subpath: params.subpath.replaceAll("-", "/"),
                shortname: params.shortname,
                resource_type: params.resourceType,
            };
        }
    }

    return { url, payload: gotoPayload };
}

/**
 * Handles complete shortname update process.
 * Returns navigation info so the caller (.svelte file) can perform routing.
 */
export async function updateEntryShortname(params: {
    space_name: string;
    subpath: string;
    oldShortname: string;
    newShortname: string;
    resourceType: ResourceType;
}): Promise<{ url: string; payload: Record<string, string> } | null> {
    // Validate new shortname
    const validation = validateShortname(params.newShortname);
    if (!validation.isValid) {
        throw new Error(validation.error);
    }

    // Skip if shortname hasn't changed
    if (!params.newShortname || params.newShortname === params.oldShortname) {
        return null;
    }

    // Perform the move operation
    await moveEntry(params);

    // Return navigation info for the caller to handle routing
    return generateNavigationInfo({
        space_name: params.space_name,
        subpath: params.subpath,
        shortname: params.newShortname,
        resourceType: params.resourceType
    });
}

/**
 * Extracts error message from API response
 */
export function extractApiErrorMessage(error: any): string {
    return error.response?.data?.error?.info?.[0]?.failed?.[0]?.error 
        || error.response?.data?.error?.message 
        || "An error occurred while processing the request.";
}