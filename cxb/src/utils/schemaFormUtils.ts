/**
 * Schema form utility functions for manipulating schema structures
 */

/**
 * Adds a new property to the form content at the specified parent path
 */
export function addProperty(formContent: any, parentPath = ""): any {
    // Handle undefined or null formContent
    if (!formContent || typeof formContent !== 'object') {
        formContent = { type: "object", properties: [], required: [] };
    }

    const newProperty = {
        id: crypto.randomUUID(),
        name: "",
        type: "string",
        title: "",
        description: ""
    };

    if (parentPath) {
        const parent = getPropertyByPath(formContent, parentPath);
        if (parent && !parent.properties) {
            parent.properties = [];
        }
        if (parent) {
            parent.properties.push(newProperty);
        }
    } else {
        if (!formContent.properties) {
            formContent.properties = [];
        }
        formContent.properties.push(newProperty);
    }

    return { ...formContent };
}

/**
 * Adds an array item to the specified parent path
 */
export function addArrayItem(formContent: any, parentPath: string): any {
    const parent = getPropertyByPath(formContent, parentPath);
    if (parent) {
        if (!parent.items) {
            parent.items = {
                id: crypto.randomUUID(),
                type: "string"
            };
        }

        if (parent.items.type === "object" && !parent.items.properties) {
            parent.items.properties = [];
        }
    }

    return { ...formContent };
}

/**
 * Removes a property at the specified path and index
 */
export function removeProperty(formContent: any, path: string, index: number): any {
    const parts = path.split('.');
    let current = formContent;

    for (let i = 0; i < parts.length - 1; i++) {
        if (!current[parts[i]]) return formContent;
        current = current[parts[i]];
    }

    const lastPart = parts[parts.length - 1];
    if (!current[lastPart]) return formContent;

    current[lastPart].splice(index, 1);
    return { ...formContent };
}

/**
 * Gets a property by its path in the form content
 */
export function getPropertyByPath(obj: any, path: string): any | null {
    const parts = path.split('.');
    let current = obj;

    for (const part of parts) {
        if (!current[part]) return null;
        current = current[part];
    }

    return current;
}

/**
 * Toggles the required status of a property
 */
export function toggleRequired(formContent: any, propertyName: string): any {
    if (!formContent.required) {
        formContent.required = [];
    }

    const index = formContent.required.indexOf(propertyName);
    if (index > -1) {
        formContent.required.splice(index, 1);
    } else {
        formContent.required.push(propertyName);
    }

    return { ...formContent };
}

/**
 * Available schema types for form fields
 */
export const schemaTypes = [
    { value: "string", name: "String" },
    { value: "number", name: "Number" },
    { value: "integer", name: "Integer" },
    { value: "boolean", name: "Boolean" },
    { value: "object", name: "Object" },
    { value: "array", name: "Array" },
    { value: "null", name: "Null" }
];

/**
 * Creates a default schema content structure
 */
export function createDefaultSchemaContent(): any {
    return {
        type: "object",
        properties: {},
        required: []
    };
}