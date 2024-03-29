// import { parsePath } from 'immutable-json-patch';

// declare enum ValidationSeverity {
//     info = "info",
//     warning = "warning",
//     error = "error"
// }

// export function normalizeAjvError(json, ajvError) {
//     return {
//         path: parsePath(json, ajvError.instancePath),
//         message: ajvError.message || 'Unknown error',
//         severity: ValidationSeverity.warning
//     };
// }

// /**
//  * Improve the error message of a JSON schema error,
//  * for example list the available values of an enum.
//  *
//  * @param {Object} ajvError
//  * @return {Object} Returns the error with improved message
//  */
// export function improveAjvError(ajvError) {
//     if (ajvError.keyword === 'enum' && Array.isArray(ajvError.schema)) {
//         let enums = ajvError.schema;
//         if (enums) {
//             enums = enums.map((value) => JSON.stringify(value));
//             if (enums.length > 5) {
//                 const more = ['(' + (enums.length - 5) + ' more...)'];
//                 enums = enums.slice(0, 5);
//                 enums.push(more);
//             }
//             ajvError.message = 'should be equal to one of: ' + enums.join(', ');
//         }
//     }
//     if (ajvError.keyword === 'additionalProperties') {
//         ajvError.message = 'should NOT have additional property: ' + ajvError.params.additionalProperty;
//     }
//     return ajvError;
// }