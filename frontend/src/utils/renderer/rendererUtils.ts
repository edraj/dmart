export function cleanUpSchema(obj: Object) {
    for (let prop in obj) {
        if (prop === "comment") delete obj[prop];
        else if (typeof obj[prop] === "object") cleanUpSchema(obj[prop]);
    }
}