import {writable} from "svelte/store";
import type {ApiResponseRecord} from "@edraj/tsdmart";

export const bulkBucket = writable<ApiResponseRecord[]>([]);
