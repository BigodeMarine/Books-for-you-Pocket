import { request } from "@/lib/api/client";
import type { ExternalBookRead, PaginatedResponse } from "@/types/api";
import { toQueryString } from "./query-params";

export interface SearchExternalBooksParams {
  title?: string | null;
  author?: string | null;
  isbn?: string | null;
  page?: number | null;
  page_size?: number | null;
}

export function searchExternalBooks(
  params: SearchExternalBooksParams,
): Promise<PaginatedResponse<ExternalBookRead>> {
  return request(`/external-books/search${toQueryString(params)}`);
}
