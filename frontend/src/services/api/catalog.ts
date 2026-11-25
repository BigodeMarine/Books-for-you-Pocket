import { request } from "@/lib/api/client";
import type {
  AvailabilityStatus,
  OfferCondition,
  OfferRead,
  PaginatedResponse,
  WorkDetailRead,
  WorkListItemRead,
  WorkType,
} from "@/types/api";
import { toQueryString } from "./query-params";

export interface ListWorksParams {
  q?: string | null;
  author_id?: string | null;
  genre_id?: string | null;
  work_type?: WorkType | null;
  page?: number | null;
  page_size?: number | null;
}

export interface ListOffersParams {
  seller_id?: string | null;
  condition?: OfferCondition | null;
  availability_status?: AvailabilityStatus | null;
  page?: number | null;
  page_size?: number | null;
}

export function listWorks(
  params: ListWorksParams = {},
): Promise<PaginatedResponse<WorkListItemRead>> {
  return request(`/catalog/works${toQueryString(params)}`);
}

export function getWork(workId: string): Promise<WorkDetailRead> {
  return request(`/catalog/works/${encodeURIComponent(workId)}`);
}

export function listEditionOffers(
  editionId: string,
  params: ListOffersParams = {},
): Promise<PaginatedResponse<OfferRead>> {
  return request(
    `/catalog/editions/${encodeURIComponent(editionId)}/offers${toQueryString(params)}`,
  );
}

export function listWorkOffers(
  workId: string,
  params: ListOffersParams = {},
): Promise<PaginatedResponse<OfferRead>> {
  return request(
    `/catalog/works/${encodeURIComponent(workId)}/offers${toQueryString(params)}`,
  );
}
