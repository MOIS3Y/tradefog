/** Shared bounded collection contracts. */
import type { paths } from "@/api/schema";

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export type ListParams = NonNullable<
  paths["/api/v1/catalog/assets"]["get"]["parameters"]["query"]
>;
