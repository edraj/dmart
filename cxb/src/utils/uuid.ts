/**
 * @deprecated Use crypto.randomUUID() directly instead.
 */
export function generateUUID(): string {
  return crypto.randomUUID();
}
