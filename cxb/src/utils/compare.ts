export function isDeepEqual(x, y) {
  if (x === y) {
    return true;
  } else if (
    typeof x == "object" &&
    x != null &&
    typeof y == "object" &&
    y != null
  ) {
    if (Object.keys(x).length != Object.keys(y).length) {
      return false;
    }

    for (var prop in x) {
      if (y.hasOwnProperty(prop)) {
        if (!isDeepEqual(x[prop], y[prop])) {
          return false;
        }
      } else {
        return false;
      }
    }

    return true;
  } else {
    return false;
  }
}

export const removeEmpty = (obj) => {
  // Handle arrays specifically
  if (Array.isArray(obj)) {
    return obj.map(item =>
        typeof item === 'object' && item !== null ? removeEmpty(item) : item
    );
  }

  let newObj = {};
  Object.keys(obj).forEach((key) => {
    if (Array.isArray(obj[key])) {
      // Preserve arrays (including empty arrays)
      newObj[key] = obj[key].map(item =>
          typeof item === 'object' && item !== null ? removeEmpty(item) : item
      );
    } else if (obj[key] === Object(obj[key]) && obj[key] !== null) {
      // Handle nested objects
      newObj[key] = removeEmpty(obj[key]);
    } else if (
        obj[key] !== undefined &&
        obj[key] !== null &&
        typeof obj[key] === "string" &&
        obj[key].trim().length != 0
    ) {
      newObj[key] = obj[key];
    } else if (
        obj[key] !== undefined &&
        obj[key] !== null &&
        typeof obj[key] !== "string"
    ) {
      newObj[key] = obj[key];
    }
  });
  return newObj;
};
