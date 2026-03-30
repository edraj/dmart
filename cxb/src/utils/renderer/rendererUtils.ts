export function generateObjectFromSchema(schema) {
    if (schema.type === 'object' && schema.properties) {
        const generatedObject = {};
        Object.keys(schema.properties).forEach((property) => {
            const propertySchema = schema.properties[property];
            if (propertySchema.type === 'object') {
                generatedObject[property] = generateObjectFromSchema(propertySchema);
                if (generatedObject[property] === undefined) {
                    generatedObject[property] = {};
                }
            } else if (propertySchema.type === 'array' && propertySchema.items) {
                generatedObject[property] = [generateObjectFromSchema(propertySchema.items)];
                if (generatedObject[property][0] === undefined) {
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

export function generateSchemaFromObject(obj: any): any {
    if (obj === null || obj === undefined) {
        return { type: "string" }; // default fallback
    }

    if (Array.isArray(obj)) {
        if (obj.length > 0) {
            return {
                type: "array",
                items: generateSchemaFromObject(obj[0])
            };
        }
        return { type: "array", items: { type: "string" } };
    }

    if (typeof obj === 'object') {
        const properties: Record<string, any> = {};
        Object.keys(obj).forEach(key => {
            properties[key] = generateSchemaFromObject(obj[key]);
        });
        return {
            type: "object",
            properties
        };
    }

    if (typeof obj === 'number') {
        return Number.isInteger(obj) ? { type: "integer" } : { type: "number" };
    }

    if (typeof obj === 'boolean') {
        return { type: "boolean" };
    }

    return { type: "string" };
}

export function scrollToElById(elementId: string) {
    const el = document.getElementById(elementId);
    if (el) {
        el.scrollIntoView({ behavior: "smooth" });
    }
}