export function isDeepEqual(x: unknown, y: unknown): boolean {
  if (x === y) {
    return true;
  } else if (
    typeof x === "object" &&
    x != null &&
    typeof y === "object" &&
    y != null
  ) {
    if (Object.keys(x).length !== Object.keys(y).length) {
      return false;
    }

    for (const prop in x) {
      if (Object.prototype.hasOwnProperty.call(y, prop)) {
        if (!isDeepEqual((x as Record<string, unknown>)[prop], (y as Record<string, unknown>)[prop])) {
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

export function removeEmpty(obj: unknown[]): unknown[];
export function removeEmpty(obj: Record<string, unknown>): Record<string, unknown>;
export function removeEmpty(obj: Record<string, unknown> | unknown[]): Record<string, unknown> | unknown[];
export function removeEmpty(obj: Record<string, unknown> | unknown[]): Record<string, unknown> | unknown[] {
  // Handle arrays specifically
  if (Array.isArray(obj)) {
    return obj.map(item =>
        typeof item === 'object' && item !== null ? removeEmpty(item as Record<string, unknown>) : item
    );
  }

  const newObj: Record<string, unknown> = {};
  Object.keys(obj).forEach((key) => {
    if (Array.isArray(obj[key])) {
      // Preserve arrays (including empty arrays)
      newObj[key] = (obj[key] as unknown[]).map(item =>
          typeof item === 'object' && item !== null ? removeEmpty(item as Record<string, unknown>) : item
      );
    } else if (obj[key] === Object(obj[key]) && obj[key] !== null) {
      // Handle nested objects
      newObj[key] = removeEmpty(obj[key] as Record<string, unknown>);
    } else if (
        obj[key] !== undefined &&
        obj[key] !== null &&
        typeof obj[key] === "string" &&
        (obj[key] as string).trim().length !== 0
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
}
