import { request } from "@/lib/api/client";
import type { OfferRead, PaginatedResponse, PriceHistoryRead } from "@/types/api";
import { toQueryString } from "./query-params";

export interface ListPriceHistoryParams {
  captured_from?: string | null;
  captured_to?: string | null;
  page?: number | null;
  page_size?: number | null;
}

export function getOffer(offerId: string): Promise<OfferRead> {
  return request(`/catalog/offers/${encodeURIComponent(offerId)}`);
}

export function listOfferPriceHistory(
  offerId: string,
  params: ListPriceHistoryParams = {},
): Promise<PaginatedResponse<PriceHistoryRead>> {
  return request(
    `/catalog/offers/${encodeURIComponent(offerId)}/price-history${toQueryString(params)}`,
  );
}
