import {writable} from "svelte/store";
import type {ApiResponseRecord} from "@edraj/tsdmart";

export const spaces = writable<ApiResponseRecord[] | null>(null);
