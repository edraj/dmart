import {ResourceType, ResponseEntry, retrieve_entry} from "@/dmart";
import {Level, showToast} from "@/utils/toast";
import {createAjvValidator} from "svelte-jsoneditor";

export function cleanUpSchema(obj: Object) {
    for (let prop in obj) {
        if (prop === "comment") delete obj[prop];
        else if (typeof obj[prop] === "object") cleanUpSchema(obj[prop]);
    }
}

export function generateObjectFromSchema(schema){
    if (schema.type === 'object' && schema.properties) {
        const generatedObject = {};
        Object.keys(schema.properties).forEach((property) => {
            const propertySchema = schema.properties[property];
            if (propertySchema.type === 'object') {
                generatedObject[property] = generateObjectFromSchema(propertySchema);
                if( generatedObject[property] === undefined){
                    generatedObject[property] = {};
                }
            } else if (propertySchema.type === 'array' && propertySchema.items) {
                generatedObject[property] = [generateObjectFromSchema(propertySchema.items)];
                if( generatedObject[property] === undefined){
                    generatedObject[property] = [];
                }
            } else {
                if (propertySchema.type === 'string') {
                    generatedObject[property] = "";
                } else if (propertySchema.type === 'number') {
                    generatedObject[property] = 0;
                } else if (propertySchema.type === 'integer') {
                    generatedObject[property] = 0;
                } else if (propertySchema.type === 'boolean') {
                    generatedObject[property] = true;
                } else {

                    generatedObject[property] = null;
                }
            }
        });
        return generatedObject;
    }
}

export const managementEntities = [
    "management/users",
    "management/roles",
    "management/permissions",
    "management/groups",
    "management/workflows",
    "/schema",
];

export function resolveResourceType(space_name:string, subpath:string ,resourceType: ResourceType) {
    const fullSubpath = `${space_name}/${subpath}`;
    switch (fullSubpath) {
        case "management/users":
            return ResourceType.user;
        case "management/roles":
            return ResourceType.role;
        case "management/permissions":
            return ResourceType.permission;
        case "management/groups":
            return ResourceType.group;
    }
    return fullSubpath.endsWith("/schema") ? ResourceType.schema : resourceType;
}

export async function get_schema(space_name:string, schema_shortname:string) {
    try {
        const schema_data: ResponseEntry | null = await retrieve_entry(
            ResourceType.schema,
            space_name,
            "/schema",
            schema_shortname,
            true,
            false
        );
        if (schema_data === null){
            return  null;
        }
        if (schema_data?.payload?.body) {
            const schema = schema_data.payload.body;
            cleanUpSchema(schema.properties);
            return {
                schema: schema,
                validator: createAjvValidator({ schema })
            }
        } else {
            return null;
        }
    }
    catch (x) {
        showToast(Level.warn, "Schema loading failed");
        return  null;
    }
}