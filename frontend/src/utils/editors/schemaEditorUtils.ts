// FORM -> JSON
import {generateUUID} from "@/utils/uuid";

export function transformToProperBodyRequest(obj: any) {
    delete obj.id;
    if (typeof obj !== "object") {
        return obj;
    }

    if (Array.isArray(obj)) {
        return obj.map(transformToProperBodyRequest);
    }

    for (const key in obj) {
        if (key !== "id") {
            obj[key] = transformToProperBodyRequest(obj[key]);
        }
        if (key === "properties") {
            obj.properties = convertArrayToObject(obj.properties);
        }
    }
    return obj;
}

export function convertArrayToObject(arr) {
    if (!Array.isArray(arr)) {
        return arr;
    }
    const obj = {};

    for (const item of arr) {
        const key = item["name"];
        delete item.name;
        obj[key] = item;
    }
    return obj;
}


export function setProperPropsForObjectOfTypeArray(obj) {
    for (let prop in obj) {
        if (typeof obj[prop] === "object") {
            setProperPropsForObjectOfTypeArray(obj[prop]);
            if (obj[prop].type === "array") {
                const object = (obj[prop].properties ?? []).reduce((acc, current) => {
                    const key = current.name;
                    delete current.name;
                    acc[key] = {...current};
                    return acc;
                }, {});
                obj[prop].items.properties = {
                    ...object,
                };

                delete obj[prop].properties;
            }
        }
    }
    return obj;
}
export function addItemsToArrays(obj) {
    for (let prop in obj) {
        if (typeof obj[prop] === "object") {
            addItemsToArrays(obj[prop]);
            if (obj[prop].type === "array") {
                obj[prop].items = {
                    type: "object",
                    properties: [],
                };
            }
        }
    }
    return obj;
}

// JSON -> FORM

export function transformFromProperBodyRequest(obj: any) {
    if (!obj || typeof obj !== "object") {
        return obj;
    }
    if (obj.id === undefined){
        obj.id = generateUUID();
    }
    if (Array.isArray(obj)) {
        return obj.map(transformFromProperBodyRequest);
    }

    const result = { ...obj };
    for (const key in result) {
        if (key !== "id") {
            result[key] = transformFromProperBodyRequest(result[key]);
        }
        if (key === "properties") {
            result.properties = convertObjectToArray(result.properties);
        }
    }

    return result;
}

export function convertObjectToArray(obj) {
    if (!obj || typeof obj !== "object") {
        return obj;
    }

    const arr = [];

    for (const key in obj) {
        if (key !== "id" && obj.hasOwnProperty(key)) {
            const item = { name: key, ...obj[key] };
            arr.push(item);
        }
    }

    return arr;
}