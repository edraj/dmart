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
  let newObj = {};
  Object.keys(obj).forEach((key) => {
    if (obj[key] === Object(obj[key])) newObj[key] = removeEmpty(obj[key]);
    else if (
      obj[key] !== undefined &&
      typeof obj[key] === "string" &&
      obj[key].trim().length != 0
    ) {
      newObj[key] = obj[key];
    }
  });
  return newObj;
};
