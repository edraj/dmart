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